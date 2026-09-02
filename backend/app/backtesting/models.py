from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.risk.models import RiskDecision
from app.strategy.models import StrategyDirection, StrategyName

from .config import BacktestConfig


class BacktestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class BacktestStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExitReason(StrEnum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_EXIT = "time_exit"
    INVALIDATION = "invalidation"
    BACKTEST_END = "backtest_end"


class PositionState(StrEnum):
    FILLED = "filled"
    ACTIVE = "active"
    CLOSED = "closed"


class LifecycleEvent(BacktestModel):
    timestamp: datetime
    state: str
    detail: str


class DataQualityReport(BacktestModel):
    valid: bool = True
    candles_checked: int = Field(default=0, ge=0)
    missing_periods: dict[str, list[datetime]] = Field(default_factory=dict)
    invalid_candles: dict[str, list[str]] = Field(default_factory=dict)
    duplicate_candles: dict[str, list[datetime]] = Field(default_factory=dict)
    insufficient_history: list[str] = Field(default_factory=list)
    unavailable_timeframes: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class BacktestPosition(BacktestModel):
    position_id: UUID
    symbol: str
    direction: StrategyDirection
    strategy: StrategyName
    entry_timestamp: datetime
    entry_price: float = Field(gt=0)
    theoretical_entry: float = Field(gt=0)
    quantity: float = Field(gt=0)
    notional: float = Field(gt=0)
    leverage: float = Field(ge=0)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    initial_risk: float = Field(gt=0)
    state: PositionState = PositionState.ACTIVE
    exit_timestamp: datetime | None = None
    exit_price: float | None = Field(default=None, gt=0)
    exit_reason: ExitReason | None = None
    gross_pnl: float = 0
    fees: float = Field(default=0, ge=0)
    slippage_cost: float = Field(default=0, ge=0)
    funding_cost: float = Field(default=0, ge=0)
    net_pnl: float = 0
    r_multiple: float = 0
    maximum_favorable_excursion: float = Field(default=0, ge=0)
    maximum_adverse_excursion: float = Field(default=0, ge=0)
    opportunity_score: float = Field(ge=0, le=100)
    setup_score: float = Field(ge=0, le=100)
    market_regime: str = "unknown"
    factor_snapshot: dict[str, Any] = Field(default_factory=dict)
    risk_decision: RiskDecision
    lifecycle: list[LifecycleEvent] = Field(default_factory=list)


class BacktestTrade(BacktestModel):
    trade_id: UUID
    backtest_id: UUID
    symbol: str
    strategy: StrategyName
    direction: StrategyDirection
    setup_score: float
    opportunity_score: float
    entry: float
    stop: float
    target: float
    exit: float
    quantity: float
    notional: float
    leverage: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: ExitReason
    gross_pnl: float
    fees: float
    slippage: float
    funding: float
    net_pnl: float
    r_multiple: float
    duration_minutes: float = Field(ge=0)
    maximum_favorable_excursion: float = Field(ge=0)
    maximum_adverse_excursion: float = Field(ge=0)
    market_regime: str
    factor_snapshot: dict[str, Any]
    strategy_version: str
    risk_decision: RiskDecision
    lifecycle: list[LifecycleEvent]


class EquityPoint(BacktestModel):
    timestamp: datetime
    equity: float
    drawdown: float = Field(ge=0)
    drawdown_percent: float = Field(ge=0)
    daily_pnl: float


class MetricSet(BacktestModel):
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0
    net_pnl: float = 0
    profit_factor: float | None = None
    expectancy: float = 0
    average_r: float = 0
    maximum_drawdown: float = 0


class PerformanceMetrics(MetricSet):
    initial_equity: float
    final_equity: float
    total_return_percent: float
    annualized_return_percent: float | None = None
    average_trade: float = 0
    median_trade: float = 0
    average_win: float = 0
    average_loss: float = 0
    largest_win: float = 0
    largest_loss: float = 0
    median_r: float = 0
    maximum_drawdown_percent: float = 0
    average_drawdown: float = 0
    maximum_consecutive_losses: int = 0
    maximum_consecutive_wins: int = 0


class ExecutionMetrics(BacktestModel):
    total_fees: float = Field(default=0, ge=0)
    total_slippage: float = Field(default=0, ge=0)
    average_slippage: float = Field(default=0, ge=0)
    average_entry_slippage: float = Field(default=0, ge=0)
    average_exit_slippage: float = Field(default=0, ge=0)
    average_trade_duration_minutes: float = Field(default=0, ge=0)
    funding_included: bool = False


class PeriodMetrics(MetricSet):
    period: str
    return_percent: float = 0
    drawdown: float = 0
    daily_loss_limit_events: int = 0


class BacktestCounters(BacktestModel):
    periods_evaluated: int = 0
    setups_detected: int = 0
    risk_approved_setups: int = 0
    risk_rejected_setups: int = 0
    entry_attempts: int = 0
    entries_filled: int = 0
    exits: int = 0


class BacktestResult(BacktestModel):
    backtest_id: UUID
    status: BacktestStatus
    configuration: BacktestConfig
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    data_quality: DataQualityReport = DataQualityReport()
    counters: BacktestCounters = BacktestCounters()
    performance: PerformanceMetrics | None = None
    execution_metrics: ExecutionMetrics | None = None
    risk_metrics: dict[str, Any] = Field(default_factory=dict)
    strategy_metrics: dict[str, MetricSet] = Field(default_factory=dict)
    direction_metrics: dict[str, MetricSet] = Field(default_factory=dict)
    symbol_metrics: dict[str, MetricSet] = Field(default_factory=dict)
    regime_metrics: dict[str, MetricSet] = Field(default_factory=dict)
    score_analysis: dict[str, MetricSet] = Field(default_factory=dict)
    setup_analysis: dict[str, MetricSet] = Field(default_factory=dict)
    r_distribution: dict[str, int] = Field(default_factory=dict)
    monthly_results: list[PeriodMetrics] = Field(default_factory=list)
    daily_results: list[PeriodMetrics] = Field(default_factory=list)
    trades: list[BacktestTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    drawdown_curve: list[EquityPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class BacktestCreateRequest(BacktestModel):
    configuration: BacktestConfig
