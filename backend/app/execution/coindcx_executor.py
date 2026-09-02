from datetime import UTC, datetime

from app.execution.interface import TradeExecutor
from app.services.coindcx.exceptions import CoinDCXError

from .exceptions import ProtectionFailure, UnknownOrderState
from .models import ExecutionIntent, ExecutionState, LiveOrder, OrderState, ProtectionStatus
from .reconciliation import normalize_exchange_position
from .state_machine import transition
from .tpsl_manager import TPSLManager


class CoinDCXTradeExecutor(TradeExecutor):
    """Exchange adapter. Its caller must pass the final safety gate before invocation."""

    def __init__(self, client, repository):
        self.client = client
        self.repository = repository
        self.tpsl = TPSLManager(client, repository)

    async def execute_entry(self, intent: ExecutionIntent, order_payload: dict):
        intent = transition(intent, ExecutionState.SUBMITTING)
        await self.repository.save_intent(intent)
        order = LiveOrder(
            execution_request_id=intent.execution_request_id,
            pair=intent.exchange_pair,
            side=order_payload["side"],
            requested_quantity=intent.quantity,
            remaining_quantity=intent.quantity,
            status=OrderState.SUBMITTING,
        )
        await self.repository.save_order(order)
        try:
            response = await self.client.create_order(order_payload)
        except UnknownOrderState:
            unknown = order.model_copy(update={"status": OrderState.UNKNOWN, "updated_at": datetime.now(UTC)})
            await self.repository.save_order(unknown)
            intent = transition(intent, ExecutionState.ORDER_UNKNOWN)
            await self.repository.save_intent(intent)
            raise
        except CoinDCXError:
            rejected = order.model_copy(update={"status": OrderState.REJECTED, "updated_at": datetime.now(UTC)})
            await self.repository.save_order(rejected)
            failed = intent.model_copy(update={"state": ExecutionState.FAILED, "updated_at": datetime.now(UTC)})
            await self.repository.save_intent(failed)
            raise
        exchange_order_id = self._extract_order_id(response)
        if not exchange_order_id:
            unknown = order.model_copy(update={"status": OrderState.UNKNOWN, "raw_metadata": {"response_shape": type(response).__name__}})
            await self.repository.save_order(unknown)
            intent = transition(intent, ExecutionState.ORDER_UNKNOWN)
            await self.repository.save_intent(intent)
            raise UnknownOrderState("CoinDCX response did not identify the order; reconciliation required")
        rows = await self.client.orders(status="open,partially_filled,filled,rejected,cancelled")
        raw = next((row for row in rows if str(row.get("id")) == exchange_order_id), None)
        if raw is None:
            unknown = order.model_copy(update={
                "exchange_order_id": exchange_order_id, "status": OrderState.UNKNOWN,
                "updated_at": datetime.now(UTC),
            })
            await self.repository.save_order(unknown)
            intent = transition(intent, ExecutionState.ORDER_UNKNOWN).model_copy(
                update={"exchange_order_id": exchange_order_id}
            )
            await self.repository.save_intent(intent)
            raise UnknownOrderState("submitted order was not confirmed by order-status query")
        filled = max(0.0, float(raw.get("total_quantity") or 0) - float(raw.get("remaining_quantity") or 0))
        status = self._order_status(str(raw.get("status") or ""))
        order = order.model_copy(update={
            "exchange_order_id": exchange_order_id,
            "filled_quantity": filled,
            "remaining_quantity": float(raw.get("remaining_quantity") or 0),
            "average_price": float(raw.get("avg_price") or 0) or None,
            "fees": float(raw.get("fee_amount") or 0),
            "status": status,
            "raw_metadata": {"status": raw.get("status"), "group_id": raw.get("group_id")},
            "updated_at": datetime.now(UTC),
        })
        await self.repository.save_order(order)
        if filled <= 0:
            return intent.model_copy(update={"state": ExecutionState.ORDER_OPEN, "exchange_order_id": exchange_order_id}), order, None
        position_rows = await self.client.positions(pairs=intent.exchange_pair)
        raw_position = next((row for row in position_rows if float(row.get("active_pos") or 0) != 0), None)
        if raw_position is None:
            unknown = order.model_copy(update={"status": OrderState.UNKNOWN})
            await self.repository.save_order(unknown)
            unknown_intent = intent.model_copy(update={
                "state": ExecutionState.ORDER_UNKNOWN,
                "exchange_order_id": exchange_order_id,
                "actual_quantity": filled,
                "updated_at": datetime.now(UTC),
            })
            await self.repository.save_intent(unknown_intent)
            raise UnknownOrderState("fill was reported but exchange position was not found")
        position = normalize_exchange_position(raw_position, execution_request_id=intent.execution_request_id)
        await self.repository.save_position(position)
        next_state = ExecutionState.PARTIALLY_FILLED if status == OrderState.PARTIALLY_FILLED else ExecutionState.FILLED
        intent = intent.model_copy(update={
            "state": next_state,
            "exchange_order_id": exchange_order_id,
            "exchange_position_id": position.exchange_position_id,
            "actual_quantity": position.quantity,
            "actual_entry": position.average_price,
            "actual_fees": order.fees,
            "updated_at": datetime.now(UTC),
        })
        await self.repository.save_intent(intent)
        pending = intent.model_copy(update={"state": ExecutionState.PROTECTION_PENDING})
        await self.repository.save_intent(pending)
        try:
            position = await self.tpsl.protect(position, intent.stop, intent.target)
            protected = pending.model_copy(update={"state": ExecutionState.PROTECTED})
            await self.repository.save_intent(protected)
            return protected, order, position
        except ProtectionFailure:
            failed_position = position.model_copy(update={"protection_status": ProtectionStatus.FAILED})
            await self.repository.save_position(failed_position)
            exiting = pending.model_copy(update={"state": ExecutionState.EXIT_REQUESTED})
            await self.repository.save_intent(exiting)
            try:
                await self.client.exit_position(position.exchange_position_id)
            except Exception:  # noqa: BLE001 - any emergency-exit failure is critical
                critical = exiting.model_copy(update={"state": ExecutionState.CRITICAL})
                await self.repository.save_intent(critical)
                raise ProtectionFailure("CRITICAL_UNPROTECTED_POSITION: emergency exit failed")
            raise ProtectionFailure("native TP/SL failed; emergency exit submitted")

    async def execute_exit(self, position):
        return await self.client.exit_position(position.exchange_position_id)

    async def cancel_order(self, order):
        if not order.exchange_order_id:
            raise ValueError("exchange order id is required")
        return await self.client.cancel_order(order.exchange_order_id)

    @staticmethod
    def _extract_order_id(response) -> str | None:
        if isinstance(response, list) and response:
            return str(response[0].get("id")) if response[0].get("id") else None
        if isinstance(response, dict):
            row = response.get("data", response)
            if isinstance(row, dict) and row.get("id"):
                return str(row["id"])
        return None

    @staticmethod
    def _order_status(value: str) -> OrderState:
        return {
            "open": OrderState.OPEN,
            "partially_filled": OrderState.PARTIALLY_FILLED,
            "filled": OrderState.FILLED,
            "cancelled": OrderState.CANCELLED,
            "rejected": OrderState.REJECTED,
        }.get(value.lower(), OrderState.UNKNOWN)
