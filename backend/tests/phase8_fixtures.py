from datetime import UTC, datetime, timedelta

from app.backtesting.config import BacktestConfig
from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from tests.phase7_fixtures import instrument

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candle(index=0, *, open=100, high=101, low=99, close=100, timeframe=Timeframe.MINUTE_5):
    return NormalizedCandle(
        symbol="B-TEST_USDT",
        timeframe=timeframe,
        timestamp=NOW + timedelta(seconds=index * int(_duration(timeframe).total_seconds())),
        open=open,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def _duration(timeframe):
    from app.market_data.normalization import TIMEFRAME_DURATION

    return TIMEFRAME_DURATION[timeframe]


def config(**updates):
    values = {
        "symbols": ("B-TEST_USDT",),
        "start_timestamp": NOW,
        "end_timestamp": NOW + timedelta(days=1),
        "instrument_overrides": {"B-TEST_USDT": instrument()},
    }
    values.update(updates)
    return BacktestConfig(**values)
