from datetime import UTC, datetime, timedelta

from app.domain.market import Candle, Timeframe
from app.services.candles import CandleService


def test_aggregate_5m_to_15m_preserves_ohlcv():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows = [
        Candle(
            time=start + timedelta(minutes=5 * i),
            open=100 + i,
            high=102 + i,
            low=99 + i,
            close=101 + i,
            volume=10 + i,
        )
        for i in range(3)
    ]
    result = CandleService.aggregate(rows, Timeframe.MINUTE_15)
    assert len(result) == 1
    assert (result[0].open, result[0].high, result[0].low, result[0].close, result[0].volume) == (
        100,
        104,
        99,
        103,
        33,
    )


def test_week_buckets_begin_monday():
    candle = Candle(
        time=datetime(2025, 1, 8, 12, tzinfo=UTC), open=1, high=2, low=1, close=2, volume=1
    )
    result = CandleService.aggregate([candle], Timeframe.WEEK_1)
    assert result[0].time == datetime(2025, 1, 6, tzinfo=UTC)


async def test_history_uses_cache_for_same_market_bucket():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows = [
        Candle(time=start, open=1, high=2, low=1, close=2, volume=10),
        Candle(time=start + timedelta(minutes=5), open=2, high=3, low=2, close=3, volume=10),
    ]

    class Client:
        calls = 0

        async def get_candles(self, *args):
            self.calls += 1
            return rows

    class Cache:
        value = None

        async def get(self, _key):
            return self.value

        async def set(self, _key, candles, _ttl):
            self.value = candles

    client, cache = Client(), Cache()
    service = CandleService(client, cache)
    first = await service.history(
        "B-BTC_USDT", Timeframe.MINUTE_5, 2, end=start + timedelta(hours=1)
    )
    second = await service.history(
        "B-BTC_USDT", Timeframe.MINUTE_5, 2, end=start + timedelta(hours=1)
    )
    assert first == second == rows
    assert client.calls == 1
