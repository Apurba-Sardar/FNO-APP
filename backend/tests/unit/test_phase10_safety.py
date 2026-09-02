from datetime import UTC, datetime, timedelta

import pytest

from app.execution.config import LiveExecutionConfig
from app.execution.instrument import InstrumentMapper
from app.execution.models import CircuitState, LiveAccount, LivePosition, ProtectionStatus
from app.execution.order_manager import CoinDCXOrderRequestBuilder
from app.execution.safety import EmergencyStop, ExecutionCircuitBreaker, LiveSafetyGate
from app.market_data.models import Market, MarketType
from app.risk.models import RiskDecision, RiskDecisionStatus, RiskLockState
from app.strategy.models import StrategyDirection, StrategyName, StrategyResult, StrategyStatus

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def market():
    return Market(symbol="B-BTC_USDT", base_asset="BTC", quote_asset="USDT", market_type=MarketType.FUTURES, status="active", min_quantity=0.001, min_notional=5, step_size=0.001, tick_size=0.1)


def setup():
    return StrategyResult.model_construct(
        symbol="B-BTC_USDT", strategy=StrategyName.TREND_PULLBACK,
        status=StrategyStatus.TRIGGERED, direction=StrategyDirection.LONG,
        evaluation_timestamp=NOW - timedelta(seconds=5), expires_at=NOW + timedelta(minutes=5),
        hypothetical_entry=100.0, hypothetical_stop=98.0, hypothetical_target=104.0,
    )


def decision():
    return RiskDecision.model_construct(
        symbol="B-BTC_USDT", strategy=StrategyName.TREND_PULLBACK,
        direction=StrategyDirection.LONG, allowed=True, status=RiskDecisionStatus.APPROVED,
        evaluation_timestamp=NOW - timedelta(seconds=2), position_quantity=0.1,
        position_notional=10.0, estimated_leverage=1.0, risk_amount=0.2,
        estimated_fees=0.01, estimated_slippage_cost=0.01,
    )


def gate_kwargs():
    return {
        "confirmation": "confirm", "emergency_stop": EmergencyStop(),
        "circuit_breaker": ExecutionCircuitBreaker(), "runtime_ready": True,
        "risk_lock": RiskLockState.OPEN,
        "account": LiveAccount(equity=1000, available_balance=900, daily_pnl=0, timestamp=NOW),
        "setup": setup(), "decision": decision(), "current_price": 100.05,
        "market_fresh": True, "market_active": True, "api_healthy": True,
        "credentials_available": True, "open_positions": [], "orders_today": 0,
        "trades_today": 0, "total_exposure": 0, "quantity_valid": True,
        "prices_valid": True, "instrument_valid": True, "leverage_verified": True,
        "margin_mode_verified": True, "now": NOW,
    }


def test_instrument_mapping_uses_exchange_metadata_and_floors_quantity():
    assert InstrumentMapper.exchange_pair("BTC_USDT", market()) == "B-BTC_USDT"
    assert InstrumentMapper.floor_quantity(0.1009, market()) == 0.1
    with pytest.raises(ValueError):
        InstrumentMapper.exchange_pair("ETH_USDT", market())


def test_order_builder_has_no_browser_controlled_risk_fields():
    built = CoinDCXOrderRequestBuilder().build_market(setup(), decision(), market())
    assert built.payload["pair"] == "B-BTC_USDT"
    assert built.payload["total_quantity"] == 0.1
    assert built.payload["order_type"] == "market_order"
    assert "stop" not in built.payload and "target" not in built.payload
    assert "time_in_force" not in built.payload


def test_all_live_gates_pass_only_with_full_explicit_configuration():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="confirm", stage=3)
    result = LiveSafetyGate(config).evaluate(**gate_kwargs())
    assert result.passed
    assert len(result.checks) >= 20


@pytest.mark.parametrize("mutation,reason", [
    ({"confirmation": "wrong"}, "confirmation"),
    ({"market_fresh": False}, "stale"),
    ({"orders_today": 3}, "order"),
    ({"trades_today": 1}, "trade"),
])
def test_critical_gate_failures_block(mutation, reason):
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="confirm", stage=3)
    values = gate_kwargs() | mutation
    result = LiveSafetyGate(config).evaluate(**values)
    assert not result.passed
    assert any(reason in item.lower() for item in result.reasons)


def test_emergency_circuit_and_unprotected_position_each_block():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="confirm", stage=3)
    values = gate_kwargs()
    values["emergency_stop"].trigger()
    values["circuit_breaker"].state = CircuitState.OPEN
    values["open_positions"] = [LivePosition(
        exchange_position_id="p1", pair="B-ETH_USDT", direction=StrategyDirection.LONG,
        quantity=1, average_price=10, leverage=1, margin_mode="isolated",
        protection_status=ProtectionStatus.UNPROTECTED,
    )]
    result = LiveSafetyGate(config).evaluate(**values)
    assert not result.passed
    names = {item.name for item in result.checks if not item.passed}
    assert {"EMERGENCY_STOP", "CIRCUIT_BREAKER", "NO_UNPROTECTED"} <= names
