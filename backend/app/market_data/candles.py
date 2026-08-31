from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Protocol

import structlog

from app.domain.market import Timeframe
from app.services.coindcx.public_client import CoinDCXPublicClient

from .cache import RedisMarketDataStore
from .models import CandleResult, CandleValidationIssue, NormalizedCandle
from .normalization import TIMEFRAME_DURATION, normalize_rest_candles


class CandlePersistence(Protocol):
    async def save(self, candles: list[NormalizedCandle]) -> int: ...


class HistoricalCandleService:
    source_resolution: ClassVar[dict[Timeframe, tuple[str, timedelta]]] = {
        Timeframe.MINUTE_5: ("5", timedelta(minutes=5)),
        Timeframe.MINUTE_15: ("5", timedelta(minutes=5)),
        Timeframe.HOUR_1: ("60", timedelta(hours=1)),
        Timeframe.HOUR_4: ("60", timedelta(hours=1)),
        Timeframe.DAY_1: ("1D", timedelta(days=1)),
        Timeframe.WEEK_1: ("1D", timedelta(days=1)),
    }

    def __init__(
        self,
        client: CoinDCXPublicClient,
        *,
        cache: RedisMarketDataStore | None = None,
        repository: CandlePersistence | None = None,
        cache_ttl_seconds: int = 30,
    ) -> None:
        self.client = client
        self.cache = cache
        self.repository = repository
        self.cache_ttl_seconds = cache_ttl_seconds

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int,
        *,
        end: datetime | None = None,
    ) -> CandleResult:
        if not 1 <= limit <= 1000:
            raise ValueError("candle limit must be between 1 and 1000")
        if self.cache and (cached := await self.cache.get_candles(symbol, timeframe.value, limit)):
            latest = cached.candles[-1].timestamp if cached.candles else None
            now = (end or datetime.now(UTC)).astimezone(UTC)
            cached.stale = latest is None or now - latest > TIMEFRAME_DURATION[timeframe] * 2
            if not cached.stale:
                return cached

        end = (end or datetime.now(UTC)).astimezone(UTC)
        resolution, source_delta = self.source_resolution[timeframe]
        factor = max(1, int(TIMEFRAME_DURATION[timeframe] / source_delta))
        start = end - source_delta * (limit * factor + factor + 2)
        structlog.get_logger().info(
            "CANDLE_FETCH", symbol=symbol, timeframe=timeframe.value, limit=limit
        )
        raw = await self.client.candlesticks(
            symbol, int(start.timestamp()), int(end.timestamp()), resolution
        )
        source_timeframe = self._source_timeframe(resolution)
        normalized = normalize_rest_candles(symbol, source_timeframe, raw, now=end)
        if source_timeframe != timeframe:
            candles = self.aggregate(normalized.candles, timeframe)
        else:
            candles = normalized.candles
        candles = candles[-limit:]
        stale = not candles or end - candles[-1].timestamp > TIMEFRAME_DURATION[timeframe] * 2
        issues = list(normalized.validation_issues)
        if stale and not any(issue.reason == "latest candle is stale" for issue in issues):
            issues.append(CandleValidationIssue(reason="latest candle is stale"))
        result = CandleResult(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            validation_issues=issues,
            stale=stale,
        )
        if self.repository:
            try:
                await self.repository.save(candles)
            except Exception as exc:  # noqa: BLE001 - persistence is isolated from market reads
                structlog.get_logger().error(
                    "CANDLE_PERSISTENCE_ERROR", symbol=symbol, error=str(exc)
                )
        if self.cache:
            await self.cache.set_candles(result, self.cache_ttl_seconds)
            if candles:
                await self.cache.set_latest_candle(candles[-1])
        return result

    async def get_latest_candle(self, symbol: str, timeframe: Timeframe) -> NormalizedCandle | None:
        result = await self.get_candles(symbol, timeframe, 2)
        return result.candles[-1] if result.candles else None

    @classmethod
    def aggregate(
        cls, candles: list[NormalizedCandle], timeframe: Timeframe
    ) -> list[NormalizedCandle]:
        groups: OrderedDict[datetime, list[NormalizedCandle]] = OrderedDict()
        for candle in sorted(candles, key=lambda item: item.timestamp):
            bucket = cls._bucket_start(candle.timestamp, timeframe)
            groups.setdefault(bucket, []).append(candle)
        return [
            NormalizedCandle(
                symbol=items[0].symbol,
                timeframe=timeframe,
                timestamp=bucket,
                open=items[0].open,
                high=max(item.high for item in items),
                low=min(item.low for item in items),
                close=items[-1].close,
                volume=sum(item.volume for item in items),
            )
            for bucket, items in groups.items()
        ]

    @staticmethod
    def _bucket_start(moment: datetime, timeframe: Timeframe) -> datetime:
        if timeframe == Timeframe.WEEK_1:
            day = moment.astimezone(UTC) - timedelta(days=moment.weekday())
            return day.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds = int(TIMEFRAME_DURATION[timeframe].total_seconds())
        epoch = int(moment.timestamp())
        return datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC)

    @staticmethod
    def _source_timeframe(resolution: str) -> Timeframe:
        return {"5": Timeframe.MINUTE_5, "60": Timeframe.HOUR_1, "1D": Timeframe.DAY_1}[resolution]
