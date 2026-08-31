import pytest

from app.indicators import IndicatorEngine


def test_ema_seeds_with_sma_and_continues():
    result = IndicatorEngine.ema([1, 2, 3, 4, 5], 3)
    assert result == [None, None, 2, 3, 4]


def test_rsi_is_100_for_monotonic_gains():
    result = IndicatorEngine.rsi(list(range(20)), 14)
    assert result[-1] == 100


def test_atr_accounts_for_gaps(candles):
    result = IndicatorEngine.atr(candles, 14)
    assert result[-1] == pytest.approx(1.6)


def test_snapshot_uses_configurable_relative_volume(candles):
    snapshot = IndicatorEngine.snapshot(candles, volume_lookback=5)
    expected = candles[-1].volume / sum(x.volume for x in candles[-5:]) * 5
    assert snapshot.relative_volume == pytest.approx(expected)
    assert snapshot.ema20 is not None and snapshot.ema200 is not None
    assert snapshot.support < snapshot.resistance


def test_empty_snapshot_is_rejected():
    with pytest.raises(ValueError):
        IndicatorEngine.snapshot([])
