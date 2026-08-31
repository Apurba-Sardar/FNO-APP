from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from app.clients.coindcx import CoinDCXPublicClient
from app.domain.market import Candle, Timeframe
from app.services.cache import CandleCache


class CandleService:
    # REST documentation guarantees these source resolutions. Other requested frames are aggregated.
    source_resolution: ClassVar[dict[Timeframe, tuple[str, timedelta]]] = {
        Timeframe.MINUTE_5: ("5", timedelta(minutes=5)),
        Timeframe.MINUTE_15: ("5", timedelta(minutes=5)),
        Timeframe.HOUR_1: ("60", timedelta(hours=1)),
        Timeframe.HOUR_4: ("60", timedelta(hours=1)),
        Timeframe.DAY_1: ("1D", timedelta(days=1)),
        Timeframe.WEEK_1: ("1D", timedelta(days=1)),
    }
    target_seconds: ClassVar[dict[Timeframe, int]] = {
        Timeframe.MINUTE_5: 300,
        Timeframe.MINUTE_15: 900,
        Timeframe.HOUR_1: 3600,
        Timeframe.HOUR_4: 14400,
        Timeframe.DAY_1: 86400,
        Timeframe.WEEK_1: 604800,
    }

    def __init__(
        self,
        client: CoinDCXPublicClient,
        cache: CandleCache | None = None,
        cache_ttl_seconds: int = 30,
    ) -> None:
        self.client = client
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds

    async def history(
        self, pair: str, timeframe: Timeframe, bars: int, end: datetime | None = None
    ) -> list[Candle]:
        if bars <= 0:
            raise ValueError("bars must be positive")
        end = (end or datetime.now(UTC)).astimezone(UTC)
        cache_key = (
            f"candles:{pair}:{timeframe.value}:{bars}:"
            f"{int(end.timestamp()) // self.target_seconds[timeframe]}"
        )
        if self.cache and (cached := await self.cache.get(cache_key)) is not None:
            return cached
        resolution, source_delta = self.source_resolution[timeframe]
        factor = self.target_seconds[timeframe] // int(source_delta.total_seconds())
        start = end - source_delta * (bars * factor + factor + 2)
        raw = await self.client.get_candles(
            pair, int(start.timestamp()), int(end.timestamp()), resolution
        )
        result = raw if factor == 1 else self.aggregate(raw, timeframe)
        result = result[-bars:]
        if self.cache:
            await self.cache.set(cache_key, result, self.cache_ttl_seconds)
        return result

    @staticmethod
    def _bucket_start(moment: datetime, timeframe: Timeframe) -> datetime:
        moment = moment.astimezone(UTC)
        if timeframe == Timeframe.WEEK_1:
            day = moment - timedelta(days=moment.weekday())
            return day.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds = CandleService.target_seconds[timeframe]
        epoch = int(moment.timestamp())
        return datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC)

    @classmethod
    def aggregate(cls, candles: list[Candle], timeframe: Timeframe) -> list[Candle]:
        groups: OrderedDict[datetime, list[Candle]] = OrderedDict()
        for candle in sorted(candles, key=lambda item: item.time):
            groups.setdefault(cls._bucket_start(candle.time, timeframe), []).append(candle)
        return [
            Candle(
                time=bucket,
                open=items[0].open,
                high=max(x.high for x in items),
                low=min(x.low for x in items),
                close=items[-1].close,
                volume=sum(x.volume for x in items),
            )
            for bucket, items in groups.items()
        ]
