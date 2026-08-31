from datetime import UTC, datetime

import pytest

from app.domain.market import Timeframe
from app.market_data.normalization import (
    epoch_milliseconds,
    epoch_seconds,
    normalize_market,
    normalize_rest_candles,
)
from app.services.coindcx.models import CoinDCXCandle, CoinDCXInstrument


def test_market_normalization_uses_documented_increments():
    market = normalize_market(
        CoinDCXInstrument(
            pair="B-BTC_USDT",
            status="active",
            settle_currency_short_name="USDT",
            quote_currency_short_name="USDT",
            underlying_currency_short_name="BTC",
            kind="perpetual",
            price_increment=0.1,
            quantity_increment=0.001,
            min_quantity=0.001,
            min_notional=60,
        )
    )
    assert market.symbol == "B-BTC_USDT"
    assert market.base_asset == "BTC"
    assert market.price_precision == 1
    assert market.quantity_precision == 3
    assert market.tick_size == 0.1


def test_timestamp_units_are_explicit_and_timezone_aware():
    assert epoch_milliseconds(1_735_689_600_000) == datetime(2025, 1, 1, tzinfo=UTC)
    assert epoch_seconds(1_735_689_600) == datetime(2025, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="millisecond"):
        epoch_milliseconds(None)


def test_candle_normalization_isolates_duplicates_and_invalid_ohlc():
    timestamp = 1_735_689_600_000
    rows = [
        CoinDCXCandle(time=timestamp, open=100, high=110, low=90, close=105, volume=10),
        CoinDCXCandle(time=timestamp, open=100, high=110, low=90, close=105, volume=10),
        CoinDCXCandle(time=timestamp + 300_000, open=100, high=95, low=90, close=101, volume=10),
        CoinDCXCandle(time=timestamp + 600_000, open=100, high=110, low=90, close=105, volume=-1),
        CoinDCXCandle(time=None, open=100, high=110, low=90, close=105, volume=10),
    ]
    result = normalize_rest_candles(
        "B-BTC_USDT",
        Timeframe.MINUTE_5,
        rows,
        now=datetime(2025, 1, 1, 0, 5, tzinfo=UTC),
    )
    assert len(result.candles) == 1
    assert len(result.validation_issues) == 4
    assert any("duplicate" in issue.reason for issue in result.validation_issues)
    assert not result.stale


def test_stale_latest_candle_is_flagged():
    result = normalize_rest_candles(
        "B-BTC_USDT",
        Timeframe.MINUTE_5,
        [CoinDCXCandle(time=1_735_689_600_000, open=1, high=2, low=1, close=2, volume=1)],
        now=datetime(2025, 1, 1, 1, tzinfo=UTC),
    )
    assert result.stale
    assert result.validation_issues[-1].reason == "latest candle is stale"
