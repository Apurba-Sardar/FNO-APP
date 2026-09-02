from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.domain.market import Timeframe
from app.indicators.models import TimeframeAnalysis
from app.market_data.models import NormalizedCandle
from app.scanner.models import ScannerCandidate
from app.scoring.models import Opportunity


class StrategyModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class StrategyName(StrEnum):
    TREND_PULLBACK = "trend_pullback"
    BREAKOUT = "breakout"


class StrategyStatus(StrEnum):
    NO_SETUP = "no_setup"
    WATCH = "watch"
    ARMED = "armed"
    TRIGGERED = "triggered"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class StrategyDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NO_SETUP = "no_setup"


class SetupQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    WEAK = "weak"
    INVALID = "invalid"


class EntryMethod(StrEnum):
    CLOSED_CANDLE_CONFIRMATION = "closed_candle_confirmation"
    BREAKOUT_CLOSE = "breakout_close"


class StopMethod(StrEnum):
    STRUCTURE_ATR_BUFFER = "structure_atr_buffer"
    BREAKOUT_RECLAIM_ATR_BUFFER = "breakout_reclaim_atr_buffer"


class EntryZone(StrategyModel):
    low: float = Field(gt=0)
    high: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "EntryZone":
        if self.low > self.high:
            raise ValueError("entry zone low must not exceed high")
        return self


class StrategyCondition(StrategyModel):
    name: str
    met: bool
    explanation: str


class QualityFactor(StrategyModel):
    name: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    contribution: float = Field(ge=0, le=100)
    explanation: str


class ChartPoint(StrategyModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    ema20: float | None = Field(default=None, gt=0)
    ema50: float | None = Field(default=None, gt=0)
    vwap: float | None = Field(default=None, gt=0)


class StrategyContext(StrategyModel):
    symbol: str
    evaluation_timestamp: datetime
    opportunity: Opportunity
    market: ScannerCandidate
    timeframes: dict[Timeframe, TimeframeAnalysis]
    candles: dict[Timeframe, list[NormalizedCandle]]
    current_price: float | None = Field(default=None, gt=0)
    chart: list[ChartPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sufficient_data: bool = False


class StrategyResult(StrategyModel):
    symbol: str
    strategy: StrategyName
    status: StrategyStatus
    direction: StrategyDirection
    evaluation_timestamp: datetime
    opportunity_score: float = Field(ge=0, le=100)
    setup_quality_score: float = Field(ge=0, le=100)
    quality: SetupQuality
    entry_method: EntryMethod | None = None
    entry_zone: EntryZone | None = None
    trigger_price: float | None = Field(default=None, gt=0)
    hypothetical_entry: float | None = Field(default=None, gt=0)
    stop_method: StopMethod | None = None
    hypothetical_stop: float | None = Field(default=None, gt=0)
    hypothetical_target: float | None = Field(default=None, gt=0)
    risk_reward: float | None = Field(default=None, ge=0)
    invalidation_price: float | None = Field(default=None, gt=0)
    expires_at: datetime | None = None
    conditions: list[StrategyCondition] = Field(default_factory=list)
    quality_factors: list[QualityFactor] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def setup_type(self) -> str:
        return self.strategy.value

    @computed_field
    @property
    def entry(self) -> float | None:
        return self.hypothetical_entry

    @computed_field
    @property
    def trigger(self) -> float | None:
        return self.trigger_price

    @computed_field
    @property
    def invalidation(self) -> float | None:
        return self.invalidation_price

    @computed_field
    @property
    def expiry(self) -> datetime | None:
        return self.expires_at

    @computed_field
    @property
    def risk_distance(self) -> float | None:
        if self.hypothetical_entry is None or self.hypothetical_stop is None:
            return None
        return abs(self.hypothetical_entry - self.hypothetical_stop)

    @computed_field
    @property
    def reward_distance(self) -> float | None:
        if self.hypothetical_entry is None or self.hypothetical_target is None:
            return None
        return abs(self.hypothetical_target - self.hypothetical_entry)

    @computed_field
    @property
    def estimated_rr(self) -> float | None:
        return self.risk_reward

    @computed_field
    @property
    def conditions_met(self) -> list[str]:
        return [condition.name for condition in self.conditions if condition.met]

    @computed_field
    @property
    def conditions_failed(self) -> list[str]:
        return [condition.name for condition in self.conditions if not condition.met]


class SymbolStrategyAnalysis(StrategyModel):
    symbol: str
    evaluation_timestamp: datetime
    opportunity_score: float = Field(ge=0, le=100)
    current_price: float | None = Field(default=None, gt=0)
    timeframe_trends: dict[Timeframe, str] = Field(default_factory=dict)
    relative_volume: float | None = Field(default=None, ge=0)
    atr: float | None = Field(default=None, ge=0)
    spread_percent: float | None = Field(default=None, ge=0)
    estimated_slippage_percent: float | None = Field(default=None, ge=0)
    results: dict[StrategyName, StrategyResult]
    best_setup: StrategyResult | None = None
    chart: list[ChartPoint] = Field(default_factory=list)
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SetupSummary(StrategyModel):
    symbol: str
    strategy: StrategyName
    status: StrategyStatus
    direction: StrategyDirection
    setup_quality_score: float
    opportunity_score: float
    hypothetical_entry: float | None
    entry_zone: EntryZone | None
    trigger_price: float | None
    hypothetical_stop: float | None
    hypothetical_target: float | None
    risk_reward: float | None
    evaluation_timestamp: datetime
    expires_at: datetime | None
    warnings: list[str]

    @classmethod
    def from_result(cls, result: StrategyResult) -> "SetupSummary":
        return cls(**{field: getattr(result, field) for field in cls.model_fields})


class StrategyStatistics(StrategyModel):
    evaluated_at: datetime
    symbols_evaluated: int = Field(ge=0)
    strategies_evaluated: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    strategy_counts: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = Field(ge=0)


class StrategyEvaluationRequest(StrategyModel):
    symbol: str | None = None
    evaluation_timestamp: datetime | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
