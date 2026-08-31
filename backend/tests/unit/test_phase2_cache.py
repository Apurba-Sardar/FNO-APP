from datetime import UTC, datetime

from app.domain.market import Timeframe
from app.market_data.cache import RedisMarketDataStore
from app.market_data.models import CandleResult, NormalizedCandle


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, _ttl, value):
        self.values[key] = value

    async def ping(self):
        return True


async def test_candle_cache_round_trip_marks_cache_hit():
    store = RedisMarketDataStore(FakeRedis())
    result = CandleResult(
        symbol="B-BTC_USDT",
        timeframe=Timeframe.MINUTE_15,
        candles=[
            NormalizedCandle(
                symbol="B-BTC_USDT",
                timeframe=Timeframe.MINUTE_15,
                timestamp=datetime(2025, 1, 1, tzinfo=UTC),
                open=100,
                high=110,
                low=90,
                close=105,
                volume=10,
            )
        ],
    )
    await store.set_candles(result, 30)
    cached = await store.get_candles("B-BTC_USDT", "15m", 1)
    assert cached is not None
    assert cached.cache_hit
    assert cached.candles == result.candles
