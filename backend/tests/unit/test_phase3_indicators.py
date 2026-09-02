from datetime import UTC, datetime, timedelta
from math import nan

import pytest
from pydantic import ValidationError

from app.domain.market import Timeframe
from app.indicators.atr import atr
from app.indicators.candle import characterize
from app.indicators.ema import ema
from app.indicators.engine import IndicatorEngine
from app.indicators.exceptions import IndicatorError
from app.indicators.macd import MacdSeries, crossover, macd
from app.indicators.models import IndicatorSnapshot, VolatilityRegime
from app.indicators.rsi import rsi
from app.indicators.volume import relative_volume
from app.indicators.vwap import utc_session_vwap
from app.market_data.models import NormalizedCandle


def candle(
    index: int,
    close: float,
    *,
    volume: float = 100,
    start: datetime | None = None,
) -> NormalizedCandle:
    timestamp = (start or datetime(2025, 1, 1, tzinfo=UTC)) + timedelta(minutes=5 * index)
    return NormalizedCandle(
        symbol="B-TEST_USDT",
        timeframe=Timeframe.MINUTE_5,
        timestamp=timestamp,
        open=close - 0.25,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=volume,
    )


def test_ema_known_dataset_and_insufficient_history():
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]
    assert ema([1, 2], 3) == [None, None]


def test_ema_rejects_invalid_values():
    with pytest.raises(IndicatorError):
        ema([1, nan], 2)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (list(range(20)), 100),
        (list(range(20, 0, -1)), 0),
        ([10.0] * 20, 50),
    ],
)
def test_rsi_directional_and_flat_series(values, expected):
    assert rsi(values, 14)[-1] == expected


def test_rsi_insufficient_history_is_unavailable():
    assert all(value is None for value in rsi([1.0] * 14, 14))


def test_macd_crossover_and_insufficient_history():
    bullish, bearish = crossover(
        MacdSeries(
            macd=[None, -1, 1],
            signal=[None, 0, 0],
            histogram=[None, -1, 1],
        )
    )
    assert bullish and not bearish
    assert all(value is None for value in macd([1.0] * 20).macd)


def test_wilder_atr_known_ohlc_and_insufficient_history():
    rows = [candle(0, 100), candle(1, 103), candle(2, 102)]
    result = atr(rows, 3)
    assert result[-1] == pytest.approx((2 + 4 + 2) / 3)
    assert atr(rows[:2], 3) == [None, None]


def test_vwap_resets_at_utc_day_and_handles_zero_volume():
    start = datetime(2025, 1, 1, 23, 55, tzinfo=UTC)
    rows = [
        candle(0, 100, volume=0, start=start),
        candle(1, 110, volume=10, start=start),
    ]
    result = utc_session_vwap(rows)
    assert result[0] is None
    assert result[1] == pytest.approx((rows[1].high + rows[1].low + rows[1].close) / 3)


def test_relative_volume_and_zero_average():
    assert relative_volume([1, 1, 1, 3], 3)[-1] == pytest.approx(1.8)
    assert relative_volume([0, 0, 0], 3)[-1] is None
    assert relative_volume([1, 2], 3) == [None, None]


def test_candle_characteristics_are_deterministic():
    row = NormalizedCandle(
        symbol="B-TEST_USDT",
        timeframe=Timeframe.MINUTE_5,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        open=100,
        high=111,
        low=99,
        close=110,
        volume=10,
    )
    result = characterize(row)
    assert result.direction == "bullish"
    assert result.strong_bullish
    assert not result.doji


def test_full_engine_reports_unavailable_ema200_without_fabrication():
    start = datetime.now(UTC) - timedelta(minutes=5 * 49)
    rows = [candle(index, 100 + index * 0.1, start=start) for index in range(50)]
    result = IndicatorEngine().analyze("B-TEST_USDT", Timeframe.MINUTE_5, rows)
    assert result.indicators.ema20 is not None
    assert result.indicators.ema200 is None
    assert not result.data_quality.sufficient_data
    assert result.data_quality.analysis_completeness == 25


def test_volatility_regime_uses_centralized_thresholds():
    rows = [candle(index, 100 + index * 0.01) for index in range(220)]
    result = IndicatorEngine().analyze("B-TEST_USDT", Timeframe.MINUTE_5, rows)
    assert result.volatility.regime in set(VolatilityRegime)


def test_analysis_models_reject_nan():
    with pytest.raises(ValidationError):
        IndicatorSnapshot(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            close=100,
            volume=1,
            ema20=nan,
        )
