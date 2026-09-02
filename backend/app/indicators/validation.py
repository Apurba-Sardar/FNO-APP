from datetime import UTC, datetime, timedelta

from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION

from .models import DataQuality


def validate_candles(
    candles: list[NormalizedCandle],
    timeframe: Timeframe,
    *,
    required_candles: int,
    stale: bool = False,
    now: datetime | None = None,
    gap_tolerance: float = 1.5,
) -> DataQuality:
    warnings: list[str] = []
    invalid = 0
    duplicates = 0
    gaps = 0
    seen = set()
    previous = None
    expected = TIMEFRAME_DURATION[timeframe]
    for candle in candles:
        if candle.timeframe != timeframe:
            invalid += 1
            warnings.append(f"candle timeframe {candle.timeframe} does not match {timeframe}")
        if candle.timestamp in seen:
            duplicates += 1
        seen.add(candle.timestamp)
        if previous is not None:
            if candle.timestamp <= previous:
                warnings.append("candles are not strictly sorted")
            elif candle.timestamp - previous > expected * gap_tolerance:
                gaps += 1
        previous = candle.timestamp
    current = (now or datetime.now(UTC)).astimezone(UTC)
    stale_data = stale or not candles or current - candles[-1].timestamp > expected * 2
    if len(candles) < required_candles:
        warnings.append(
            f"{len(candles)} candles available; {required_candles} required for full analysis"
        )
    if stale_data:
        warnings.append("latest candle is stale")
    if duplicates:
        warnings.append(f"{duplicates} duplicate timestamp(s)")
    if gaps:
        warnings.append(f"{gaps} unexpected timestamp gap(s)")
    completeness = min(100.0, len(candles) / required_candles * 100)
    if invalid or duplicates:
        completeness *= max(0.0, 1 - (invalid + duplicates) / max(len(candles), 1))
    if stale_data:
        completeness *= 0.8
    return DataQuality(
        sufficient_data=len(candles) >= required_candles and not invalid and not duplicates,
        candle_count=len(candles),
        required_candles=required_candles,
        stale_data=stale_data,
        invalid_candles=invalid,
        duplicate_timestamps=duplicates,
        unexpected_gaps=gaps,
        warnings=list(dict.fromkeys(warnings)),
        analysis_completeness=round(completeness, 2),
    )


def timeframe_delta(timeframe: Timeframe) -> timedelta:
    return TIMEFRAME_DURATION[timeframe]
