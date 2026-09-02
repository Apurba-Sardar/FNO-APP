from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.domain.market import Timeframe
from app.indicators.engine import IndicatorEngine
from app.indicators.models import IndicatorSnapshot, PriceStructure, TrendState
from app.market_data.models import CandleResult, NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION


def frame_candles(timeframe: Timeframe, slope: float = 0.2) -> list[NormalizedCandle]:
    duration = TIMEFRAME_DURATION[timeframe]
    start = datetime.now(UTC) - duration * 219
    wave = [0, 1, 2, 1, 0, -1, -2, -1]
    rows = []
    for index in range(220):
        close = 100 + slope * index + wave[index % len(wave)]
        rows.append(
            NormalizedCandle(
                symbol="B-TEST_USDT",
                timeframe=timeframe,
                timestamp=start + duration * index,
                open=close - slope / 2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=100 + index % 20,
            )
        )
    return rows


def snapshot(**changes) -> IndicatorSnapshot:
    values = {
        "timestamp": datetime.now(UTC),
        "close": 110,
        "volume": 100,
        "ema20": 108,
        "ema50": 105,
        "ema200": 100,
        "price_above_ema20": True,
        "ema20_above_ema50": True,
        "ema50_above_ema200": True,
        "rsi": 60,
    }
    values.update(changes)
    return IndicatorSnapshot(**values)


@pytest.mark.parametrize(
    ("technical", "structure_trend", "expected"),
    [
        ({}, TrendState.BULLISH, TrendState.BULLISH),
        (
            {
                "close": 90,
                "price_above_ema20": False,
                "ema20_above_ema50": False,
                "ema50_above_ema200": False,
                "rsi": 40,
            },
            TrendState.BEARISH,
            TrendState.BEARISH,
        ),
        ({}, TrendState.NEUTRAL, TrendState.NEUTRAL),
        ({}, TrendState.BEARISH, TrendState.TRANSITION),
    ],
)
def test_trend_classification(technical, structure_trend, expected):
    result, strength = IndicatorEngine._trend(
        snapshot(**technical),
        PriceStructure(trend=structure_trend),
        [100.0, 101, 102, 103, 104, 105],
    )
    assert result == expected
    assert 0 <= strength <= 100


def test_all_six_timeframes_are_analyzed_without_trade_recommendations():
    frames = {
        timeframe: CandleResult(
            symbol="B-TEST_USDT",
            timeframe=timeframe,
            candles=frame_candles(timeframe),
        )
        for timeframe in Timeframe
    }
    result = MultiTimeframeAnalyzer().analyze("B-TEST_USDT", frames)
    assert set(result.timeframes) == set(Timeframe)
    assert result.data_quality.sufficient_data
    serialized = result.model_dump_json().lower()
    assert '"direction":"long"' not in serialized
    assert '"direction":"short"' not in serialized
    assert "win_probability" not in serialized


def test_timeframe_alignment_states():
    analyses = {
        timeframe: SimpleNamespace(trend=trend)
        for timeframe, trend in zip(
            Timeframe,
            [
                TrendState.BULLISH,
                TrendState.BULLISH,
                TrendState.BULLISH,
                TrendState.BULLISH,
                TrendState.BULLISH,
                TrendState.NEUTRAL,
            ],
            strict=True,
        )
    }
    result = MultiTimeframeAnalyzer.alignment(analyses)
    assert result.bullish_count == 5
    assert result.alignment_ratio == pytest.approx(5 / 6)
    assert result.alignment_state == "strongly_bullish"


def test_missing_timeframe_reduces_analysis_completeness():
    timeframe = Timeframe.MINUTE_5
    frames = {
        timeframe: CandleResult(
            symbol="B-TEST_USDT",
            timeframe=timeframe,
            candles=frame_candles(timeframe),
        )
    }
    result = MultiTimeframeAnalyzer().analyze("B-TEST_USDT", frames, list(Timeframe))
    assert len(result.data_quality.missing_timeframes) == 5
    assert not result.data_quality.sufficient_data
    assert result.data_quality.analysis_completeness == pytest.approx(100 / 6, abs=0.02)
