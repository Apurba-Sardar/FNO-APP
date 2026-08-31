from enum import StrEnum

from pydantic import BaseModel, Field


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class MarketRegime(StrEnum):
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class ScoreInputs(BaseModel):
    weekly_trend: float = Field(ge=0, le=1)
    daily_trend: float = Field(ge=0, le=1)
    four_hour_trend: float = Field(ge=0, le=1)
    one_hour_momentum: float = Field(ge=0, le=1)
    fifteen_minute_setup: float = Field(ge=0, le=1)
    volume_expansion: float = Field(ge=0, le=1)
    liquidity_order_book: float = Field(ge=0, le=1)
    volatility_atr: float = Field(ge=0, le=1)
    support_resistance: float = Field(ge=0, le=1)
    risk_reward: float = Field(ge=0, le=1)


class Opportunity(BaseModel):
    pair: str
    score: float
    direction: Direction
    status: str
    metrics: dict[str, float | str]
    reasons: list[str]
    warnings: list[str]
