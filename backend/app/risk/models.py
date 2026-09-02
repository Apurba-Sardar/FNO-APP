from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.market_data.models import Market
from app.strategy.models import StrategyDirection, StrategyName, StrategyResult


class RiskModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class RiskDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"
    ACCOUNT_DATA_UNAVAILABLE = "account_data_unavailable"
    MARKET_DATA_UNAVAILABLE = "market_data_unavailable"
    RISK_LIMIT_REACHED = "risk_limit_reached"


class RiskLockState(StrEnum):
    OPEN = "open"
    WARNING = "warning"
    BLOCKED = "blocked"


class RiskSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class OpenPosition(RiskModel):
    symbol: str
    direction: StrategyDirection
    notional: float = Field(ge=0)
    status: str = "confirmed_open"
    correlation_group: str = "broad_crypto_market"


class AccountSnapshot(RiskModel):
    account_equity: float | None = Field(default=None, gt=0)
    available_balance: float | None = Field(default=None, ge=0)
    starting_day_equity: float | None = Field(default=None, gt=0)
    realized_pnl_today: float = 0
    unrealized_pnl: float = 0
    fees_today: float = Field(default=0, ge=0)
    funding_today: float = 0
    deposits_today: float = Field(default=0, ge=0)
    withdrawals_today: float = Field(default=0, ge=0)
    consecutive_losses: int = Field(default=0, ge=0)
    consecutive_loss_reset_at: datetime | None = None
    open_positions: list[OpenPosition] = Field(default_factory=list)
    timestamp: datetime | None = None


class RiskState(RiskModel):
    account: AccountSnapshot = AccountSnapshot()
    daily_pnl: float = 0
    daily_loss: float = Field(default=0, ge=0)
    daily_loss_percent: float = Field(default=0, ge=0)
    total_exposure: float = Field(default=0, ge=0)
    exposure_percent: float = Field(default=0, ge=0)
    trading_lock: RiskLockState = RiskLockState.BLOCKED
    block_reasons: list[str] = Field(default_factory=lambda: ["account data unavailable"])
    trading_day: date | None = None
    last_updated: datetime | None = None


class RiskContext(RiskModel):
    evaluation_timestamp: datetime
    account: AccountSnapshot
    strategy_setup: StrategyResult
    instrument: Market | None = None
    current_price: float | None = Field(default=None, gt=0)
    atr: float | None = Field(default=None, gt=0)
    spread_percent: float | None = Field(default=None, ge=0)
    estimated_slippage_percent: float | None = Field(default=None, ge=0)
    market_data_timestamp: datetime | None = None
    liquidity_usable: bool = False
    correlation_group: str = "broad_crypto_market"


class RiskCheck(RiskModel):
    name: str
    passed: bool
    value: Any = None
    threshold: Any = None
    severity: RiskSeverity
    explanation: str


class RiskDecision(RiskModel):
    symbol: str
    strategy: StrategyName
    direction: StrategyDirection
    allowed: bool
    status: RiskDecisionStatus
    evaluation_timestamp: datetime
    risk_amount: float = Field(default=0, ge=0)
    risk_percent: float = Field(default=0, ge=0)
    position_quantity: float = Field(default=0, ge=0)
    position_notional: float = Field(default=0, ge=0)
    estimated_leverage: float = Field(default=0, ge=0)
    required_margin: float = Field(default=0, ge=0)
    remaining_available_margin: float | None = None
    estimated_liquidation_price: float | None = None
    estimated_fees: float = Field(default=0, ge=0)
    estimated_slippage_cost: float = Field(default=0, ge=0)
    stop_loss_risk: float = Field(default=0, ge=0)
    maximum_loss: float = Field(default=0, ge=0)
    estimated_reward: float = 0
    estimated_rr: float = Field(default=0, ge=0)
    entry_drift_percent: float | None = Field(default=None, ge=0)
    exposure_percent_after: float = Field(default=0, ge=0)
    correlated_exposure_warning: bool = False
    maximum_trade_duration_minutes: int = Field(ge=1)
    warnings: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    checks: list[RiskCheck] = Field(default_factory=list)


class RiskStatistics(RiskModel):
    evaluated_at: datetime
    setups_evaluated: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)
    warning: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    rejection_counts: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = Field(ge=0)


class SymbolRiskAnalysis(RiskModel):
    symbol: str
    evaluation_timestamp: datetime
    decisions: dict[StrategyName, RiskDecision]


class RiskDecisionSummary(RiskModel):
    symbol: str
    strategy: StrategyName
    direction: StrategyDirection
    allowed: bool
    status: RiskDecisionStatus
    risk_amount: float
    position_quantity: float
    position_notional: float
    maximum_loss: float
    estimated_rr: float
    rejection_reasons: list[str]
    evaluation_timestamp: datetime

    @classmethod
    def from_decision(cls, decision: RiskDecision) -> "RiskDecisionSummary":
        return cls(**{field: getattr(decision, field) for field in cls.model_fields})


class RiskEvaluationRequest(RiskModel):
    symbol: str | None = None
    strategy: StrategyName | None = None
    evaluation_timestamp: datetime | None = None
    account: AccountSnapshot | None = None
    instrument: Market | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
