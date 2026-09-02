import secrets
from datetime import UTC, datetime

from app.risk.models import RiskDecision, RiskLockState
from app.strategy.models import StrategyResult, StrategyStatus

from .config import ExecutionStage, LiveExecutionConfig
from .models import (
    CircuitState,
    EmergencyStopState,
    GateCheck,
    GateResult,
    LiveAccount,
    LivePosition,
    ProtectionStatus,
)


class EmergencyStop:
    def __init__(self, triggered: bool = False):
        self.state = EmergencyStopState.TRIGGERED if triggered else EmergencyStopState.ARMED

    @property
    def triggered(self) -> bool:
        return self.state == EmergencyStopState.TRIGGERED

    def trigger(self) -> None:
        self.state = EmergencyStopState.TRIGGERED

    def resume(self) -> None:
        self.state = EmergencyStopState.ARMED


class ExecutionCircuitBreaker:
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0

    def success(self) -> None:
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED

    def failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            self.state = CircuitState.OPEN

    def half_open(self) -> None:
        self.state = CircuitState.HALF_OPEN


class LiveSafetyGate:
    def __init__(self, config: LiveExecutionConfig):
        self.config = config

    def evaluate(
        self,
        *,
        confirmation: str,
        emergency_stop: EmergencyStop,
        circuit_breaker: ExecutionCircuitBreaker,
        runtime_ready: bool,
        risk_lock: RiskLockState,
        account: LiveAccount,
        setup: StrategyResult,
        decision: RiskDecision,
        current_price: float | None,
        market_fresh: bool,
        market_active: bool,
        api_healthy: bool,
        credentials_available: bool,
        open_positions: list[LivePosition],
        orders_today: int,
        trades_today: int,
        total_exposure: float,
        quantity_valid: bool,
        prices_valid: bool,
        instrument_valid: bool,
        leverage_verified: bool,
        margin_mode_verified: bool,
        now: datetime | None = None,
    ) -> GateResult:
        now = now or datetime.now(UTC)
        risk_age = (now - decision.evaluation_timestamp).total_seconds()
        setup_age = (now - setup.evaluation_timestamp).total_seconds()
        expected = setup.hypothetical_entry
        drift = abs(current_price - expected) / expected * 100 if current_price and expected else None
        active_positions = [position for position in open_positions if position.status == "open"]
        unprotected = [
            position for position in active_positions
            if position.protection_status != ProtectionStatus.PROTECTED
        ]
        daily_loss_percent = (
            max(0.0, -account.daily_pnl / account.equity * 100) if account.equity else float("inf")
        )
        checks = [
            GateCheck(name="LIVE_MODE", passed=self.config.trading_mode == "live", detail="TRADING_MODE must be live"),
            GateCheck(name="LIVE_ENABLED", passed=self.config.enabled, detail="LIVE_TRADING_ENABLED must be true"),
            GateCheck(name="LIVE_STAGE", passed=self.config.stage >= ExecutionStage.MANUAL_TINY, detail="execution requires rollout stage 3 or higher"),
            GateCheck(name="CONFIG_CONFIRMATION", passed=bool(self.config.confirmation) and secrets.compare_digest(confirmation, self.config.confirmation), detail="live safety confirmation is invalid"),
            GateCheck(name="EMERGENCY_STOP", passed=not emergency_stop.triggered, detail="emergency stop is active"),
            GateCheck(name="CIRCUIT_BREAKER", passed=circuit_breaker.state == CircuitState.CLOSED, detail="execution circuit breaker is open"),
            GateCheck(name="RUNTIME_READY", passed=runtime_ready, detail="startup reconciliation and operator arming are required"),
            GateCheck(name="RISK_LOCK", passed=risk_lock == RiskLockState.OPEN, detail="Phase 7 risk lock is not open"),
            GateCheck(name="ACCOUNT_FRESH", passed=account.timestamp is not None and 0 <= (now - account.timestamp).total_seconds() <= self.config.max_risk_decision_age_seconds, detail="live account snapshot is stale"),
            GateCheck(name="MARKET_FRESH", passed=market_fresh, detail="market data is stale"),
            GateCheck(name="SETUP_VALID", passed=setup.status == StrategyStatus.TRIGGERED and setup.direction == decision.direction, detail="strategy setup is no longer triggered or direction changed"),
            GateCheck(name="SETUP_FRESH", passed=setup_age >= 0 and setup.expires_at is not None and now < setup.expires_at, detail="strategy setup is stale or expired"),
            GateCheck(name="RISK_VALID", passed=decision.allowed, detail="latest Phase 7 risk decision rejected execution"),
            GateCheck(name="RISK_FRESH", passed=0 <= risk_age <= self.config.max_risk_decision_age_seconds, detail="risk decision is stale"),
            GateCheck(name="ENTRY_DRIFT", passed=drift is not None and drift <= self.config.max_entry_drift_percent, detail="entry price drift exceeds live limit"),
            GateCheck(name="POSITION_LIMIT", passed=len(active_positions) < self.config.max_open_positions, detail="live open-position limit reached"),
            GateCheck(name="EXPOSURE_LIMIT", passed=total_exposure + decision.position_notional <= self.config.max_total_exposure, detail="live total-exposure limit reached"),
            GateCheck(name="NOTIONAL_LIMIT", passed=decision.position_notional <= self.config.max_notional_per_trade, detail="live per-trade notional limit reached"),
            GateCheck(name="DAILY_LOSS", passed=daily_loss_percent < self.config.max_daily_loss_percent, detail="live daily-loss limit reached"),
            GateCheck(name="ORDER_LIMIT", passed=orders_today < self.config.max_orders_per_day, detail="live daily-order limit reached"),
            GateCheck(name="TRADE_LIMIT", passed=trades_today < self.config.max_trades_per_day, detail="live daily-trade limit reached"),
            GateCheck(name="NO_UNPROTECTED", passed=not unprotected, detail="an unprotected live position blocks new entries"),
            GateCheck(name="QUANTITY_VALID", passed=quantity_valid and decision.position_quantity > 0, detail="quantity violates instrument constraints"),
            GateCheck(name="PRICE_VALID", passed=prices_valid, detail="entry/stop/target are invalid"),
            GateCheck(name="INSTRUMENT", passed=instrument_valid and market_active, detail="instrument mapping or market status is invalid"),
            GateCheck(name="LEVERAGE", passed=leverage_verified, detail="position leverage cannot be verified"),
            GateCheck(name="MARGIN_MODE", passed=margin_mode_verified, detail="position margin mode cannot be verified"),
            GateCheck(name="CREDENTIALS", passed=credentials_available, detail="CoinDCX credentials are unavailable"),
            GateCheck(name="API_HEALTH", passed=api_healthy, detail="CoinDCX authenticated API is unhealthy"),
            GateCheck(name="TPSL", passed=setup.hypothetical_stop is not None and setup.hypothetical_target is not None, detail="native TP/SL parameters are unavailable"),
        ]
        return GateResult(passed=all(item.passed for item in checks), checks=checks)
