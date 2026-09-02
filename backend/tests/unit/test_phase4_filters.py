from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.indicators.models import TrendState
from app.market_data.models import OrderBookSnapshot
from app.scanner.config import ScannerConfig
from app.scanner.filters import (
    analyze_liquidity,
    classify_direction,
    classify_technical_activity,
    classify_volatility,
    classify_volume,
    estimate_slippage_percent,
    spread_percent,
)
from app.scanner.models import (
    LiquidityClassification,
    ScannerDirection,
    TechnicalActivity,
    VolatilitySuitability,
    VolumeActivity,
)


def book(*, spread: float = 0.02, depth: float = 2_000, stale: bool = False):
    midpoint = 100
    bid, ask = midpoint - spread / 2, midpoint + spread / 2
    timestamp = datetime.now(UTC) - (timedelta(minutes=2) if stale else timedelta())
    return OrderBookSnapshot(
        symbol="B-TEST_USDT",
        timestamp=timestamp,
        bids=[(bid, depth / bid), (bid - 0.01, depth / bid)],
        asks=[(ask, depth / ask), (ask + 0.01, depth / ask)],
    )


def test_spread_and_slippage_calculations():
    snapshot = book()
    assert spread_percent(snapshot) == pytest.approx(0.02)
    assert estimate_slippage_percent(snapshot.asks, 1_000) == 0
    assert estimate_slippage_percent([], 1_000) is None


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        (book(depth=200_000), LiquidityClassification.EXCELLENT),
        (book(spread=0.06, depth=30_000), LiquidityClassification.GOOD),
        (book(spread=0.15, depth=5_000), LiquidityClassification.ACCEPTABLE),
        (book(depth=700), LiquidityClassification.POOR),
        (book(spread=1), LiquidityClassification.UNUSABLE),
        (None, LiquidityClassification.UNUSABLE),
    ],
)
def test_liquidity_classification(snapshot, expected):
    evaluation_time = snapshot.timestamp if snapshot is not None else datetime.now(UTC)
    assert (
        analyze_liquidity(snapshot, ScannerConfig(), now=evaluation_time).classification
        == expected
    )


def test_stale_orderbook_has_unknown_metrics():
    result = analyze_liquidity(book(stale=True), ScannerConfig())
    assert result.spread_status == "unknown"
    assert result.classification == "unusable"


@pytest.mark.parametrize(
    ("relative", "expected"),
    [(0.5, "quiet"), (1.0, "normal"), (1.5, "active"), (2.0, "high_activity"), (3.0, "extreme")],
)
def test_volume_activity(relative, expected):
    result = classify_volume(10, 10, relative, "increasing", ScannerConfig())
    assert result.activity == expected


@pytest.mark.parametrize(
    ("atr_percent", "expected"),
    [(0.05, "too_low"), (1.0, "suitable"), (3.0, "high"), (6.0, "extreme"), (None, "unknown")],
)
def test_volatility_suitability(atr_percent, expected):
    result = classify_volatility(1, atr_percent, 1, "normal", ScannerConfig())
    assert result.suitability == expected


def analysis_with(trends, ratio=0.7):
    values = {
        timeframe: SimpleNamespace(trend=trend, momentum=None)
        for timeframe, trend in zip(Timeframe, trends, strict=False)
    }
    return SimpleNamespace(
        timeframes=values,
        alignment=SimpleNamespace(
            bullish_count=trends.count(TrendState.BULLISH),
            bearish_count=trends.count(TrendState.BEARISH),
            alignment_ratio=ratio,
        ),
    )


def test_direction_does_not_force_conflicting_evidence():
    assert classify_direction(analysis_with([TrendState.BULLISH] * 4)) == ScannerDirection.BULLISH
    assert classify_direction(analysis_with([TrendState.BEARISH] * 4)) == ScannerDirection.BEARISH
    assert (
        classify_direction(analysis_with([TrendState.BULLISH, TrendState.BEARISH]))
        == ScannerDirection.MIXED
    )
    assert classify_direction(analysis_with([TrendState.NEUTRAL], 0)) == ScannerDirection.NEUTRAL


def test_technical_activity_is_not_a_trade_signal():
    volume = classify_volume(20, 10, 2, "increasing", ScannerConfig())
    volatility = classify_volatility(1, 1, 1.3, "normal", ScannerConfig())
    analysis = analysis_with([TrendState.BULLISH] * 4)
    analysis.timeframes[Timeframe.HOUR_1].momentum = SimpleNamespace(price_momentum="positive")
    assert (
        classify_technical_activity(analysis, volume, volatility) == TechnicalActivity.HIGH_ACTIVITY
    )
    assert volume.activity == VolumeActivity.HIGH_ACTIVITY
    assert volatility.suitability == VolatilitySuitability.SUITABLE


from app.domain.market import Timeframe
