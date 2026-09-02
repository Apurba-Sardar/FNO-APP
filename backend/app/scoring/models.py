from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.scanner.models import (
    LiquidityClassification,
    TechnicalActivity,
    VolatilitySuitability,
)


class ScoringModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class FactorName(StrEnum):
    WEEKLY_TREND = "weekly_trend"
    DAILY_TREND = "daily_trend"
    FOUR_HOUR_TREND = "four_hour_trend"
    ONE_HOUR_MOMENTUM = "one_hour_momentum"
    FIFTEEN_MINUTE_SETUP = "fifteen_minute_setup"
    VOLUME_EXPANSION = "volume_expansion"
    LIQUIDITY_ORDER_BOOK = "liquidity_order_book"
    VOLATILITY_ATR = "volatility_atr"
    SUPPORT_RESISTANCE = "support_resistance"
    RISK_REWARD = "risk_reward"


class FactorStatus(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNAVAILABLE = "unavailable"


class OpportunityDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class OpportunityTier(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ScoreFactor(ScoringModel):
    factor_name: FactorName
    raw_value: dict[str, Any] = Field(default_factory=dict)
    normalized_score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=100)
    weighted_contribution: float = Field(ge=0, le=100)
    status: FactorStatus
    explanation: str
    warnings: list[str] = Field(default_factory=list)


class Opportunity(ScoringModel):
    symbol: str
    scan_timestamp: datetime
    calculated_at: datetime
    opportunity_score: float = Field(ge=0, le=100)
    long_score: float = Field(ge=0, le=100)
    short_score: float = Field(ge=0, le=100)
    dominant_direction: OpportunityDirection
    tier: OpportunityTier
    eligible: bool
    hard_gate_reasons: list[str] = Field(default_factory=list)
    factors: list[ScoreFactor] = Field(default_factory=list)
    long_factors: list[ScoreFactor] = Field(default_factory=list)
    short_factors: list[ScoreFactor] = Field(default_factory=list)
    strongest_factors: list[str] = Field(default_factory=list)
    weakest_factors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explanation_summary: str
    estimated_structural_rr: float | None = Field(default=None, ge=0)
    long_estimated_structural_rr: float | None = Field(default=None, ge=0)
    short_estimated_structural_rr: float | None = Field(default=None, ge=0)
    market_activity: TechnicalActivity
    liquidity: LiquidityClassification
    volatility: VolatilitySuitability
    data_quality: str
    relative_volume: float | None = Field(default=None, ge=0)
    atr_percent: float | None = Field(default=None, ge=0)
    correlation_group: str = "broad_crypto_market"
    previous_score: float | None = Field(default=None, ge=0, le=100)
    score_change: float | None = None
    previous_rank: int | None = Field(default=None, ge=1)
    current_rank: int | None = Field(default=None, ge=1)
    rank_change: int | None = None


class OpportunitySummary(ScoringModel):
    symbol: str
    calculated_at: datetime
    opportunity_score: float
    long_score: float
    short_score: float
    dominant_direction: OpportunityDirection
    tier: OpportunityTier
    eligible: bool
    current_rank: int | None
    previous_rank: int | None
    rank_change: int | None
    score_change: float | None
    estimated_structural_rr: float | None
    market_activity: TechnicalActivity
    liquidity: LiquidityClassification
    volatility: VolatilitySuitability
    relative_volume: float | None
    atr_percent: float | None
    strongest_factors: list[str]
    weakest_factors: list[str]
    warnings: list[str]

    @classmethod
    def from_opportunity(cls, item: Opportunity) -> "OpportunitySummary":
        return cls(**{name: getattr(item, name) for name in cls.model_fields})


class OpportunityStatistics(ScoringModel):
    calculated_at: datetime
    markets_analyzed: int = Field(ge=0)
    eligible_opportunities: int = Field(ge=0)
    hard_gate_exclusions: int = Field(ge=0)
    calculation_time_ms: float = Field(ge=0)
    ranking_time_ms: float = Field(ge=0)
    average_scoring_time_ms: float = Field(ge=0)
    tier_counts: dict[str, int] = Field(default_factory=dict)
    direction_counts: dict[str, int] = Field(default_factory=dict)
    exclusion_counts: dict[str, int] = Field(default_factory=dict)
