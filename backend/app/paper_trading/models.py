from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.strategy.models import StrategyDirection, StrategyName


class PaperModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class ExecutionMode(StrEnum):
    PAPER = "paper"


class EngineStatus(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    DATA_STALE = "data_stale"


class PaperOrderStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PaperPositionStatus(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class PaperSetupStatus(StrEnum):
    WATCH = "watch"
    ARMED = "armed"
    TRIGGERED = "triggered"
    REJECTED_BY_RISK = "rejected_by_risk"
    ENTERED = "entered"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class PaperExitReason(StrEnum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_EXIT = "time_exit"
    INVALIDATION = "invalidation"
    MANUAL = "manual"


class FundingStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    APPLIED = "applied"


class StrategyHealthState(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    INSUFFICIENT_SAMPLE = "insufficient_sample"


class MarketQuote(PaperModel):
    symbol: str
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    last: float | None = Field(default=None, gt=0)
    timestamp: datetime

    @property
    def mid(self) -> float | None:
        return (self.bid + self.ask) / 2 if self.bid and self.ask else self.last


class PaperAccount(PaperModel):
    account_id: UUID = Field(default_factory=uuid4)
    initial_equity: float = Field(gt=0)
    equity: float = Field(gt=0)
    available_balance: float = Field(ge=0)
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    fees: float = Field(default=0, ge=0)
    slippage_cost: float = Field(default=0, ge=0)
    funding_cost: float = Field(default=0, ge=0)
    margin_used: float = Field(default=0, ge=0)
    total_exposure: float = Field(default=0, ge=0)
    peak_equity: float = Field(gt=0)
    drawdown: float = Field(default=0, ge=0)
    daily_pnl: float = 0
    starting_day_equity: float | None = Field(default=None, gt=0)
    trading_day: date | None = None
    consecutive_losses: int = Field(default=0, ge=0)
    updated_at: datetime


class PaperOrder(PaperModel):
    order_id: UUID = Field(default_factory=uuid4)
    symbol: str
    direction: StrategyDirection
    order_type: str = "market"
    quantity: float = Field(gt=0)
    requested_price: float = Field(gt=0)
    executed_price: float | None = Field(default=None, gt=0)
    status: PaperOrderStatus = PaperOrderStatus.CREATED
    created_at: datetime
    executed_at: datetime | None = None
    strategy: StrategyName
    setup_id: str
    opportunity_score: float = Field(ge=0, le=100)
    setup_score: float = Field(ge=0, le=100)
    fees: float = Field(default=0, ge=0)
    slippage: float = Field(default=0, ge=0)
    rejection_reason: str | None = None
    idempotency_key: str
    lifecycle: list[str] = Field(default_factory=list)


class PaperPosition(PaperModel):
    position_id: UUID = Field(default_factory=uuid4)
    order_id: UUID
    setup_id: str
    symbol: str
    direction: StrategyDirection
    strategy: StrategyName
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    entry_timestamp: datetime
    stop_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    current_price: float = Field(gt=0)
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    entry_fee: float = Field(default=0, ge=0)
    exit_fee: float = Field(default=0, ge=0)
    slippage: float = Field(default=0, ge=0)
    funding: float = 0
    funding_status: FundingStatus = FundingStatus.UNAVAILABLE
    maximum_favorable_excursion: float = Field(default=0, ge=0)
    maximum_adverse_excursion: float = Field(default=0, ge=0)
    initial_trade_risk: float = Field(gt=0)
    leverage: float = Field(ge=1)
    status: PaperPositionStatus = PaperPositionStatus.OPEN
    exit_price: float | None = Field(default=None, gt=0)
    exit_timestamp: datetime | None = None
    exit_reason: PaperExitReason | None = None
    opportunity_score: float = Field(ge=0, le=100)
    setup_score: float = Field(ge=0, le=100)
    market_regime: str = "unknown"
    factor_snapshot: dict[str, Any] = Field(default_factory=dict)
    protection_status: str = "protected"
    protection_lifecycle: list[str] = Field(
        default_factory=lambda: ["protection_created", "protected"]
    )

    @property
    def notional(self) -> float:
        return self.entry_price * self.quantity

    @property
    def current_r(self) -> float:
        return self.unrealized_pnl / self.initial_trade_risk


class PaperTrade(PaperModel):
    trade_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    position_id: UUID
    symbol: str
    strategy: StrategyName
    direction: StrategyDirection
    opportunity_score: float
    setup_score: float
    entry: float
    stop: float
    target: float
    quantity: float
    notional: float
    entry_fee: float
    exit_fee: float
    fees: float
    slippage: float
    funding: float
    funding_status: FundingStatus
    exit: float
    exit_reason: PaperExitReason
    gross_pnl: float
    net_pnl: float
    r_multiple: float
    duration_minutes: float
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    market_regime: str
    factor_snapshot: dict[str, Any]
    strategy_version: str
    risk_version: str
    timestamp: datetime
    evaluation_time: datetime | None = None
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    planned_entry: float | None = None
    risk_amount: float | None = None
    risk_percent: float | None = None
    risk_decision: dict[str, Any] = Field(default_factory=dict)
    strategy_explanation: list[str] = Field(default_factory=list)
    market_context: dict[str, Any] = Field(default_factory=dict)
    order_lifecycle: list[str] = Field(default_factory=list)
    protection_lifecycle: list[str] = Field(default_factory=list)
    data_quality: dict[str, Any] = Field(default_factory=dict)
    execution_quality: dict[str, Any] = Field(default_factory=dict)


class PaperSetupState(PaperModel):
    setup_id: str
    symbol: str
    strategy: StrategyName
    status: PaperSetupStatus
    trigger_timestamp: datetime
    updated_at: datetime
    reason: str | None = None


class PaperSession(PaperModel):
    session_id: UUID = Field(default_factory=uuid4)
    start_time: datetime
    end_time: datetime | None = None
    initial_equity: float
    final_equity: float | None = None
    trade_count: int = 0
    net_pnl: float = 0
    max_drawdown: float = 0
    configuration_snapshot: dict[str, Any]
    strategy_version: str
    risk_version: str


class PaperEvent(PaperModel):
    event_type: str
    timestamp: datetime
    symbol: str | None = None
    strategy: str | None = None
    setup_id: str | None = None
    position_id: UUID | None = None
    detail: str = ""


class PaperCounters(PaperModel):
    setups_detected: int = 0
    risk_approved: int = 0
    risk_rejected: int = 0
    entries: int = 0
    exits: int = 0


class PaperState(PaperModel):
    account: PaperAccount
    sessions: list[PaperSession] = Field(default_factory=list)
    orders: list[PaperOrder] = Field(default_factory=list)
    positions: list[PaperPosition] = Field(default_factory=list)
    trades: list[PaperTrade] = Field(default_factory=list)
    setups: dict[str, PaperSetupState] = Field(default_factory=dict)
    events: list[PaperEvent] = Field(default_factory=list)
    counters: PaperCounters = Field(default_factory=PaperCounters)
    cooldowns: dict[str, datetime] = Field(default_factory=dict)
    engine_status: EngineStatus = EngineStatus.STOPPED
    last_market_update: datetime | None = None
    last_scan: datetime | None = None
    last_strategy_evaluation: datetime | None = None
    last_risk_evaluation: datetime | None = None
    trading_blocked: bool = False
    block_reason: str | None = None
    state_recovery_status: str = "new"
