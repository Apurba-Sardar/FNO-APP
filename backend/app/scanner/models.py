from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.market import Timeframe
from app.indicators.models import TimeframeAnalysis
from app.market_data.models import Market, NormalizedCandle


class ScannerModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class CandidateStatus(StrEnum):
    ELIGIBLE = "eligible"
    FILTERED = "filtered"
    WARNING = "warning"
    DATA_ERROR = "data_error"
    STALE = "stale"
    INSUFFICIENT_DATA = "insufficient_data"


class ScannerRunStatus(StrEnum):
    STOPPED = "stopped"
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class LiquidityClassification(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"


class MetricStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class VolumeActivity(StrEnum):
    QUIET = "quiet"
    NORMAL = "normal"
    ACTIVE = "active"
    HIGH_ACTIVITY = "high_activity"
    EXTREME = "extreme"


class VolatilitySuitability(StrEnum):
    TOO_LOW = "too_low"
    SUITABLE = "suitable"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


class TechnicalActivity(StrEnum):
    DORMANT = "dormant"
    NORMAL = "normal"
    ACTIVE = "active"
    HIGH_ACTIVITY = "high_activity"


class ScannerDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class MarketScanMetrics(ScannerModel):
    last_price: float | None = Field(default=None, gt=0)
    price_change_percent_24h: float | None = None
    volume_24h: float | None = Field(default=None, ge=0)
    data_timestamp: datetime | None = None
    fresh: bool = False


class LiquiditySnapshot(ScannerModel):
    classification: LiquidityClassification
    spread_status: MetricStatus
    spread_percent: float | None = Field(default=None, ge=0)
    slippage_status: MetricStatus
    estimated_slippage_percent: float | None = Field(default=None, ge=0)
    bid_depth_quote: float | None = Field(default=None, ge=0)
    ask_depth_quote: float | None = Field(default=None, ge=0)
    orderbook_timestamp: datetime | None = None


class VolumeSnapshot(ScannerModel):
    current_volume: float | None = Field(default=None, ge=0)
    volume_ma: float | None = Field(default=None, ge=0)
    relative_volume: float | None = Field(default=None, ge=0)
    trend: str
    activity: VolumeActivity
    spike: bool = False


class VolatilitySnapshot(ScannerModel):
    atr: float | None = Field(default=None, ge=0)
    atr_percent: float | None = Field(default=None, ge=0)
    recent_range_expansion: float | None = Field(default=None, ge=0)
    regime: str | None = None
    suitability: VolatilitySuitability


class ScannerCandidate(ScannerModel):
    symbol: str
    scan_timestamp: datetime
    processing_duration_ms: float = Field(ge=0)
    status: CandidateStatus
    market: MarketScanMetrics
    liquidity: LiquiditySnapshot
    volume: VolumeSnapshot
    volatility: VolatilitySnapshot
    timeframes: dict[Timeframe, TimeframeAnalysis] = Field(default_factory=dict)
    # A bounded normalized candle context lets downstream deterministic analysis
    # operate without importing or calling an exchange client.
    recent_candles: dict[Timeframe, list[NormalizedCandle]] = Field(default_factory=dict)
    dominant_direction: ScannerDirection
    timeframe_alignment: str
    alignment_ratio: float = Field(ge=0, le=1)
    technical_activity: TechnicalActivity
    data_quality_status: str
    warnings: list[str] = Field(default_factory=list)
    instrument: Market | None = None


class ScannerCandidateSummary(ScannerModel):
    symbol: str
    scan_timestamp: datetime
    status: CandidateStatus
    processing_duration_ms: float
    last_price: float | None
    price_change_percent_24h: float | None
    volume_24h: float | None
    relative_volume: float | None
    spread_percent: float | None
    estimated_slippage_percent: float | None
    atr_percent: float | None
    liquidity: LiquidityClassification
    volatility: VolatilitySuitability
    trends: dict[Timeframe, str]
    dominant_direction: ScannerDirection
    timeframe_alignment: str
    technical_activity: TechnicalActivity
    warnings: list[str]

    @classmethod
    def from_candidate(cls, candidate: ScannerCandidate) -> "ScannerCandidateSummary":
        return cls(
            symbol=candidate.symbol,
            scan_timestamp=candidate.scan_timestamp,
            status=candidate.status,
            processing_duration_ms=candidate.processing_duration_ms,
            last_price=candidate.market.last_price,
            price_change_percent_24h=candidate.market.price_change_percent_24h,
            volume_24h=candidate.market.volume_24h,
            relative_volume=candidate.volume.relative_volume,
            spread_percent=candidate.liquidity.spread_percent,
            estimated_slippage_percent=candidate.liquidity.estimated_slippage_percent,
            atr_percent=candidate.volatility.atr_percent,
            liquidity=candidate.liquidity.classification,
            volatility=candidate.volatility.suitability,
            trends={
                timeframe: analysis.trend.value
                for timeframe, analysis in candidate.timeframes.items()
            },
            dominant_direction=candidate.dominant_direction,
            timeframe_alignment=candidate.timeframe_alignment,
            technical_activity=candidate.technical_activity,
            warnings=candidate.warnings,
        )


class ScannerStatistics(ScannerModel):
    scan_started_at: datetime
    scan_completed_at: datetime
    total_markets: int = Field(ge=0)
    eligible_markets: int = Field(ge=0)
    filtered_markets: int = Field(ge=0)
    warning_markets: int = Field(ge=0)
    data_errors: int = Field(ge=0)
    stale_markets: int = Field(ge=0)
    insufficient_data_markets: int = Field(ge=0)
    processing_time_seconds: float = Field(ge=0)
    average_processing_time_ms: float = Field(ge=0)
    api_requests: int = Field(default=0, ge=0)
    analysis_time_seconds: float = Field(default=0, ge=0)
    filter_counts: dict[str, int] = Field(default_factory=dict)


class SymbolScannerState(ScannerModel):
    symbol: str
    last_scan_time: datetime
    candidate: ScannerCandidate
    last_successful_scan: datetime | None = None
    last_failure: str | None = None
    failure_count: int = Field(default=0, ge=0)
    data_fresh: bool
    processing_duration_ms: float = Field(ge=0)


class ScannerStatusSnapshot(ScannerModel):
    status: ScannerRunStatus
    scheduled: bool
    interval_seconds: int
    last_scan_at: datetime | None = None
    last_error: str | None = None
    candidate_count: int = Field(default=0, ge=0)
    stats: ScannerStatistics | None = None
