from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.market import Timeframe


class AnalysisModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class TrendState(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    TRANSITION = "transition"


class VolatilityRegime(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class AlignmentState(StrEnum):
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    MIXED = "mixed"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"


class LevelType(StrEnum):
    POTENTIAL_SUPPORT = "potential_support"
    POTENTIAL_RESISTANCE = "potential_resistance"


class IndicatorParameters(AnalysisModel):
    ema_periods: tuple[int, int, int] = (20, 50, 200)
    rsi_period: int = Field(default=14, gt=1)
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = Field(default=12, gt=1)
    macd_slow: int = Field(default=26, gt=2)
    macd_signal: int = Field(default=9, gt=1)
    atr_period: int = Field(default=14, gt=1)
    volume_ma_period: int = Field(default=20, gt=1)
    elevated_volume_threshold: float = Field(default=1.5, gt=0)
    volume_spike_threshold: float = Field(default=2.0, gt=0)
    swing_window: int = Field(default=3, ge=1, le=20)
    level_cluster_tolerance_percent: float = Field(default=0.3, gt=0)
    maximum_levels: int = Field(default=3, ge=1, le=10)
    roc_periods: tuple[int, int] = (5, 10)
    low_volatility_atr_percent: float = Field(default=0.5, ge=0)
    high_volatility_atr_percent: float = Field(default=2.0, gt=0)
    extreme_volatility_atr_percent: float = Field(default=4.0, gt=0)
    minimum_candles: int = Field(default=20, ge=2)
    gap_tolerance: float = Field(default=1.5, ge=1)


class DataQuality(AnalysisModel):
    sufficient_data: bool
    candle_count: int = Field(ge=0)
    required_candles: int = Field(ge=1)
    stale_data: bool = False
    invalid_candles: int = Field(default=0, ge=0)
    duplicate_timestamps: int = Field(default=0, ge=0)
    unexpected_gaps: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    analysis_completeness: float = Field(ge=0, le=100)


class SwingPoint(AnalysisModel):
    price: float = Field(gt=0)
    timestamp: datetime


class PriceLevel(AnalysisModel):
    price: float = Field(gt=0)
    type: LevelType
    distance_percent: float
    strength: int = Field(ge=1)
    timestamp: datetime
    source: str


class PriceStructure(AnalysisModel):
    trend: TrendState
    swing_high: SwingPoint | None = None
    swing_low: SwingPoint | None = None
    higher_high: bool = False
    higher_low: bool = False
    lower_high: bool = False
    lower_low: bool = False
    support_levels: list[PriceLevel] = Field(default_factory=list)
    resistance_levels: list[PriceLevel] = Field(default_factory=list)


class CandleCharacteristics(AnalysisModel):
    body_size: float = Field(ge=0)
    upper_wick: float = Field(ge=0)
    lower_wick: float = Field(ge=0)
    total_range: float = Field(ge=0)
    body_range_ratio: float | None = Field(default=None, ge=0, le=1)
    direction: str
    close_location: float | None = Field(default=None, ge=0, le=1)
    doji: bool
    strong_bullish: bool
    strong_bearish: bool
    rejection_wick: str | None = None


class MomentumAnalysis(AnalysisModel):
    rsi_state: str
    macd_state: str
    price_momentum: str
    ema_alignment: str
    roc_5: float | None = None
    roc_10: float | None = None


class VolatilityAnalysis(AnalysisModel):
    atr: float | None = None
    atr_percent: float | None = None
    recent_range_expansion: float | None = None
    regime: VolatilityRegime | None = None


class IndicatorSnapshot(AnalysisModel):
    timestamp: datetime
    close: float = Field(gt=0)
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    ema20_above_ema50: bool | None = None
    ema50_above_ema200: bool | None = None
    price_above_ema20: bool | None = None
    price_above_ema50: bool | None = None
    price_above_ema200: bool | None = None
    rsi: float | None = Field(default=None, ge=0, le=100)
    rsi_overbought: bool | None = None
    rsi_oversold: bool | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    macd_bullish_cross: bool = False
    macd_bearish_cross: bool = False
    atr: float | None = Field(default=None, ge=0)
    atr_percent: float | None = Field(default=None, ge=0)
    vwap: float | None = Field(default=None, gt=0)
    price_above_vwap: bool | None = None
    distance_from_vwap_percent: float | None = None
    volume: float = Field(ge=0)
    volume_ma: float | None = Field(default=None, ge=0)
    relative_volume: float | None = Field(default=None, ge=0)
    volume_increasing: bool | None = None
    volume_decreasing: bool | None = None
    volume_elevated: bool | None = None
    volume_spike: bool | None = None


class TimeframeAnalysis(AnalysisModel):
    symbol: str
    timeframe: Timeframe
    timestamp: datetime | None
    indicators: IndicatorSnapshot | None
    candle: CandleCharacteristics | None
    structure: PriceStructure
    momentum: MomentumAnalysis | None
    volatility: VolatilityAnalysis | None
    trend: TrendState
    trend_strength: float = Field(ge=0, le=100)
    data_quality: DataQuality


class AlignmentSummary(AnalysisModel):
    bullish_count: int = Field(ge=0)
    bearish_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    transition_count: int = Field(ge=0)
    alignment_ratio: float = Field(ge=0, le=1)
    dominant_direction: TrendState
    alignment_state: AlignmentState


class MultiTimeframeDataQuality(AnalysisModel):
    sufficient_data: bool
    missing_timeframes: list[Timeframe] = Field(default_factory=list)
    stale_timeframes: list[Timeframe] = Field(default_factory=list)
    invalid_candles: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    analysis_completeness: float = Field(ge=0, le=100)


class MultiTimeframeAnalysis(AnalysisModel):
    symbol: str
    generated_at: datetime
    timeframes: dict[Timeframe, TimeframeAnalysis]
    alignment: AlignmentSummary
    data_quality: MultiTimeframeDataQuality
