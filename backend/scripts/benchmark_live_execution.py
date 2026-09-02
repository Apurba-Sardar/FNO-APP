from datetime import UTC, datetime, timedelta
from time import perf_counter

from app.execution.config import LiveExecutionConfig
from app.execution.models import LiveAccount
from app.execution.safety import EmergencyStop, ExecutionCircuitBreaker, LiveSafetyGate
from app.risk.models import RiskDecision, RiskDecisionStatus, RiskLockState
from app.strategy.models import StrategyDirection, StrategyName, StrategyResult, StrategyStatus


def main() -> None:
    now = datetime.now(UTC)
    setup = StrategyResult.model_construct(
        symbol="B-BTC_USDT", strategy=StrategyName.TREND_PULLBACK,
        status=StrategyStatus.TRIGGERED, direction=StrategyDirection.LONG,
        evaluation_timestamp=now, expires_at=now + timedelta(minutes=1),
        hypothetical_entry=100, hypothetical_stop=98, hypothetical_target=104,
    )
    decision = RiskDecision.model_construct(
        symbol=setup.symbol, strategy=setup.strategy, direction=setup.direction, allowed=True,
        status=RiskDecisionStatus.APPROVED, evaluation_timestamp=now,
        position_quantity=0.1, position_notional=10, risk_amount=0.2,
    )
    gate = LiveSafetyGate(LiveExecutionConfig(
        trading_mode="live", enabled=True, confirmation="benchmark", stage=3
    ))
    arguments = {
        "confirmation": "benchmark", "emergency_stop": EmergencyStop(),
        "circuit_breaker": ExecutionCircuitBreaker(), "runtime_ready": True,
        "risk_lock": RiskLockState.OPEN,
        "account": LiveAccount(equity=1000, available_balance=900, timestamp=now),
        "setup": setup, "decision": decision, "current_price": 100,
        "market_fresh": True, "market_active": True, "api_healthy": True,
        "credentials_available": True, "open_positions": [], "orders_today": 0,
        "trades_today": 0, "total_exposure": 0, "quantity_valid": True,
        "prices_valid": True, "instrument_valid": True, "leverage_verified": True,
        "margin_mode_verified": True, "now": now,
    }
    runs = 10_000
    started = perf_counter()
    for _ in range(runs):
        result = gate.evaluate(**arguments)
        if not result.passed:
            raise RuntimeError(result.reasons)
    duration = perf_counter() - started
    print({"runs": runs, "total_seconds": duration, "average_ms": duration / runs * 1000})


if __name__ == "__main__":
    main()
