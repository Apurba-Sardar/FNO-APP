from datetime import UTC, datetime

import pytest

from app.execution.coindcx_executor import CoinDCXTradeExecutor
from app.execution.exceptions import ProtectionFailure, UnknownOrderState
from app.execution.models import ExecutionIntent, ExecutionState, OrderState, ProtectionStatus
from app.execution.reconciliation import PositionReconciliationService
from app.execution.repository import InMemoryLiveRepository
from app.strategy.models import StrategyDirection, StrategyName


def intent():
    now = datetime.now(UTC)
    return ExecutionIntent(
        setup_id="B-BTC_USDT:trend_pullback:2026-01-01T00:00:00+00:00",
        risk_decision_id="risk-1", symbol="B-BTC_USDT", exchange_pair="B-BTC_USDT",
        strategy=StrategyName.TREND_PULLBACK, direction=StrategyDirection.LONG,
        quantity=0.1, expected_entry=100, stop=98, target=104, leverage=1,
        notional=10, risk_amount=0.2, estimated_fees=0.01, estimated_slippage=0.01,
        setup_timestamp=now, risk_timestamp=now, strategy_version="v1", risk_version="v1",
        state=ExecutionState.RISK_RECHECK,
    )


def position_row(quantity=0.1, stop=98, target=104):
    return {
        "id": "position-1", "pair": "B-BTC_USDT", "active_pos": quantity,
        "avg_price": 100, "mark_price": 101, "liquidation_price": 50,
        "leverage": 1, "margin_type": "isolated", "locked_margin": 10,
        "stop_loss_trigger": stop, "take_profit_trigger": target,
    }


class FilledClient:
    def __init__(self, status="filled", filled=0.1, tpsl_success=True):
        self.status = status
        self.filled = filled
        self.tpsl_success = tpsl_success
        self.exit_calls = 0

    async def create_order(self, payload):
        return [{"id": "order-1"}]

    async def orders(self, **kwargs):
        return [{
            "id": "order-1", "status": self.status, "total_quantity": 0.1,
            "remaining_quantity": 0.1 - self.filled, "avg_price": 100, "fee_amount": 0.02,
        }]

    async def positions(self, **kwargs):
        return [position_row(self.filled)]

    async def create_tpsl(self, *args):
        return {
            "stop_loss": {"id": "sl", "success": self.tpsl_success},
            "take_profit": {"id": "tp", "success": self.tpsl_success},
        }

    async def exit_position(self, position_id):
        self.exit_calls += 1
        return {"status": 200}


@pytest.mark.asyncio
@pytest.mark.parametrize("status,filled,expected", [
    ("partially_filled", 0.025, OrderState.PARTIALLY_FILLED),
    ("partially_filled", 0.05, OrderState.PARTIALLY_FILLED),
    ("filled", 0.1, OrderState.FILLED),
])
async def test_partial_and_full_fills_use_actual_exchange_quantity(status, filled, expected):
    repo = InMemoryLiveRepository()
    client = FilledClient(status, filled)
    final, order, position = await CoinDCXTradeExecutor(client, repo).execute_entry(
        intent(), {"side": "buy", "pair": "B-BTC_USDT"}
    )
    assert order.status == expected
    assert order.filled_quantity == pytest.approx(filled)
    assert position.quantity == pytest.approx(filled)
    assert position.protection_status == ProtectionStatus.PROTECTED
    assert final.state == ExecutionState.PROTECTED


@pytest.mark.asyncio
async def test_tpsl_failure_marks_unprotected_and_submits_emergency_exit():
    repo = InMemoryLiveRepository()
    client = FilledClient(tpsl_success=False)
    with pytest.raises(ProtectionFailure, match="emergency exit submitted"):
        await CoinDCXTradeExecutor(client, repo).execute_entry(
            intent(), {"side": "buy", "pair": "B-BTC_USDT"}
        )
    assert client.exit_calls == 1
    assert next(iter(repo.positions.values())).protection_status == ProtectionStatus.FAILED


class TimeoutClient(FilledClient):
    async def create_order(self, payload):
        raise UnknownOrderState("timeout")


@pytest.mark.asyncio
async def test_unknown_order_is_persisted_and_not_resubmitted():
    repo = InMemoryLiveRepository()
    with pytest.raises(UnknownOrderState):
        await CoinDCXTradeExecutor(TimeoutClient(), repo).execute_entry(
            intent(), {"side": "buy", "pair": "B-BTC_USDT"}
        )
    assert len(repo.orders) == 1
    assert next(iter(repo.orders.values())).status == OrderState.UNKNOWN
    assert next(iter(repo.intents.values())).state == ExecutionState.ORDER_UNKNOWN


class ReconcileClient:
    async def positions(self):
        return [position_row()]

    async def orders(self):
        return [{"id": "orphan-order", "pair": "B-ETH_USDT"}]


@pytest.mark.asyncio
async def test_reconciliation_detects_orphan_exchange_state_and_fails_health():
    repo = InMemoryLiveRepository()
    report = await PositionReconciliationService(ReconcileClient(), repo).reconcile({}, {})
    assert report.orphan_positions == ["position-1"]
    assert report.orphan_orders == ["orphan-order"]
    assert report.healthy is False
