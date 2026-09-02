from datetime import UTC, datetime, timedelta

from app.domain.market import Timeframe
from app.indicators.structure import analyze_structure, detect_swings
from app.indicators.validation import validate_candles
from app.market_data.models import NormalizedCandle


def rows_from_prices(prices: list[float]) -> list[NormalizedCandle]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        NormalizedCandle(
            symbol="B-TEST_USDT",
            timeframe=Timeframe.HOUR_1,
            timestamp=start + timedelta(hours=index),
            open=price,
            high=price + 0.4,
            low=price - 0.4,
            close=price,
            volume=100,
        )
        for index, price in enumerate(prices)
    ]


def test_structure_detects_higher_high_and_higher_low():
    rows = rows_from_prices([10, 12, 9, 13, 10, 14, 11, 13])
    result = analyze_structure(rows, window=1)
    assert result.higher_high
    assert result.higher_low
    assert result.trend == "bullish"


def test_structure_detects_lower_high_and_lower_low():
    rows = rows_from_prices([14, 12, 15, 11, 14, 10, 13, 11])
    result = analyze_structure(rows, window=1)
    assert result.lower_high
    assert result.lower_low
    assert result.trend == "bearish"


def test_sideways_structure_is_neutral_and_levels_are_potential():
    rows = rows_from_prices([10, 11, 9, 11, 9, 11, 9, 10])
    result = analyze_structure(rows, window=1, tolerance_percent=1)
    assert result.trend == "neutral"
    levels = result.support_levels + result.resistance_levels
    assert any(level.strength > 1 for level in levels)
    assert all(level.type.value.startswith("potential_") for level in levels)


def test_swing_window_requires_local_extrema():
    swings = detect_swings(rows_from_prices([1, 2, 3, 4, 5]), window=1)
    assert not swings.highs and not swings.lows


def test_data_quality_marks_duplicates_gaps_and_stale_data():
    rows = rows_from_prices([10, 11, 12])
    rows.append(rows[-1])
    result = validate_candles(
        rows,
        Timeframe.HOUR_1,
        required_candles=10,
        stale=True,
    )
    assert result.duplicate_timestamps == 1
    assert result.stale_data
    assert not result.sufficient_data
