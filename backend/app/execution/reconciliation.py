from datetime import UTC, datetime

from app.strategy.models import StrategyDirection

from .models import LivePosition, OrderState, ProtectionStatus, ReconciliationReport


def normalize_exchange_position(row: dict, *, execution_request_id=None) -> LivePosition:
    quantity = float(row.get("active_pos") or 0)
    average_price = float(row.get("avg_price") or 0)
    mark_price = float(row["mark_price"]) if row.get("mark_price") not in {None, ""} else None
    multiplier = 1 if quantity > 0 else -1
    return LivePosition(
        execution_request_id=execution_request_id,
        exchange_position_id=str(row["id"]),
        pair=str(row["pair"]),
        direction=StrategyDirection.LONG if quantity > 0 else StrategyDirection.SHORT,
        quantity=abs(quantity),
        average_price=average_price,
        mark_price=mark_price,
        liquidation_price=float(row["liquidation_price"]) if row.get("liquidation_price") not in {None, ""} else None,
        leverage=float(row.get("leverage") or 1),
        margin_mode=str(row.get("margin_type") or "isolated").lower(),
        margin=float(row.get("locked_margin") or 0),
        stop=float(row["stop_loss_trigger"]) if row.get("stop_loss_trigger") else None,
        target=float(row["take_profit_trigger"]) if row.get("take_profit_trigger") else None,
        protection_status=(
            ProtectionStatus.PROTECTED
            if row.get("stop_loss_trigger") and row.get("take_profit_trigger")
            else ProtectionStatus.UNPROTECTED
        ),
        unrealized_pnl=(mark_price - average_price) * abs(quantity) * multiplier if mark_price else 0,
        status="open" if quantity else "closed",
        updated_at=datetime.now(UTC),
    )


class PositionReconciliationService:
    def __init__(self, client, repository):
        self.client = client
        self.repository = repository

    async def reconcile(self, local_orders: dict, local_positions: dict) -> ReconciliationReport:
        exchange_positions = await self.client.positions()
        exchange_orders = await self.client.orders()
        active_exchange = {str(row["id"]): row for row in exchange_positions if float(row.get("active_pos") or 0) != 0}
        open_exchange_orders = {str(row["id"]): row for row in exchange_orders}
        known_positions = {item.exchange_position_id: item for item in local_positions.values() if item.status == "open"}
        known_orders = {item.exchange_order_id: item for item in local_orders.values() if item.exchange_order_id}
        report = ReconciliationReport(
            matched_positions=len(set(active_exchange) & set(known_positions)),
            matched_orders=len(set(open_exchange_orders) & set(known_orders)),
            orphan_positions=sorted(set(active_exchange) - set(known_positions)),
            ghost_positions=sorted(set(known_positions) - set(active_exchange)),
            orphan_orders=sorted(set(open_exchange_orders) - set(known_orders)),
        )
        for exchange_id, row in active_exchange.items():
            local = known_positions.get(exchange_id)
            if local:
                normalized = normalize_exchange_position(row, execution_request_id=local.execution_request_id)
                normalized = normalized.model_copy(update={"position_id": local.position_id})
                local_positions[local.position_id] = normalized
                await self.repository.save_position(normalized)
            else:
                normalized = normalize_exchange_position(row)
                local_positions[normalized.position_id] = normalized
                await self.repository.save_position(normalized)
            if normalized.protection_status == ProtectionStatus.UNPROTECTED:
                report.protection_failures.append(exchange_id)
        for exchange_id, local in known_orders.items():
            row = open_exchange_orders.get(exchange_id)
            if local.status == OrderState.UNKNOWN and row:
                local_orders[local.order_id] = local.model_copy(update={"status": OrderState.RECONCILED, "raw_metadata": row})
                await self.repository.save_order(local_orders[local.order_id])
                report.unknown_orders_resolved += 1
        report.healthy = not (report.orphan_positions or report.ghost_positions or report.orphan_orders or report.protection_failures)
        return report
