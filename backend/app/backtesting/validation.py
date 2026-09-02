from app.domain.market import Timeframe
from app.market_data.normalization import TIMEFRAME_DURATION

from .models import DataQualityReport


def validate_historical_data(
    data: dict[str, dict[Timeframe, list]], minimum_history: int = 50
) -> DataQualityReport:
    report = DataQualityReport()
    for symbol, frames in data.items():
        unavailable = []
        for timeframe in Timeframe:
            rows = frames.get(timeframe, [])
            key = f"{symbol}:{timeframe.value}"
            report.candles_checked += len(rows)
            if not rows:
                unavailable.append(timeframe.value)
                continue
            timestamps = [row.timestamp for row in rows]
            duplicates = sorted(item for item, count in Counter(timestamps).items() if count > 1)
            if duplicates:
                report.duplicate_candles[key] = duplicates
            issues = []
            for index, row in enumerate(rows):
                if row.high < max(row.open, row.close) or row.low > min(row.open, row.close):
                    issues.append(f"row {index}: impossible OHLC")
                if row.volume < 0 or min(row.open, row.high, row.low, row.close) <= 0:
                    issues.append(f"row {index}: invalid price or volume")
            if issues:
                report.invalid_candles[key] = issues
            missing = []
            duration = TIMEFRAME_DURATION[timeframe]
            for previous, current in pairwise(rows):
                cursor = previous.timestamp + duration
                while cursor < current.timestamp:
                    missing.append(cursor)
                    cursor += duration
            if missing:
                report.missing_periods[key] = missing
            if len(rows) < minimum_history:
                report.insufficient_history.append(key)
        if unavailable:
            report.unavailable_timeframes[symbol] = unavailable
    report.valid = not report.invalid_candles and not report.duplicate_candles
    if report.missing_periods:
        report.warnings.append("Missing candles are never forward-filled.")
    if report.insufficient_history:
        report.warnings.append("Some symbol/timeframe histories are below indicator warmup.")
    return report
from collections import Counter
from itertools import pairwise
