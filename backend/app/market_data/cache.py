import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .models import CandleResult, MarketTrade, NormalizedCandle, OrderBookSnapshot, Ticker


class RedisMarketDataStore:
    def __init__(self, redis: Redis, latest_ttl_seconds: int = 120) -> None:
        self.redis = redis
        self.latest_ttl_seconds = latest_ttl_seconds
        self.available = True

    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> CandleResult | None:
        raw = await self._get(f"market:{symbol}:candles:{timeframe}:history:{limit}")
        if raw is None:
            return None
        try:
            result = CandleResult.model_validate_json(raw)
            result.cache_hit = True
            return result
        except ValueError as exc:
            structlog.get_logger().warning("MARKET_CACHE_INVALID", key="candles", error=str(exc))
            return None

    async def set_candles(self, result: CandleResult, ttl_seconds: int) -> None:
        key = (
            f"market:{result.symbol}:candles:{result.timeframe.value}:history:{len(result.candles)}"
        )
        await self._set(key, result.model_dump_json(), ttl_seconds)

    async def set_latest_candle(self, candle: NormalizedCandle) -> None:
        await self._set(
            f"market:{candle.symbol}:candles:{candle.timeframe.value}",
            candle.model_dump_json(),
            self.latest_ttl_seconds,
        )

    async def set_ticker(self, ticker: Ticker) -> None:
        await self._set(
            f"market:{ticker.symbol}:ticker",
            ticker.model_dump_json(),
            self.latest_ttl_seconds,
        )

    async def get_ticker(self, symbol: str) -> Ticker | None:
        raw = await self._get(f"market:{symbol}:ticker")
        return Ticker.model_validate_json(raw) if raw else None

    async def set_orderbook(self, book: OrderBookSnapshot) -> None:
        await self._set(
            f"market:{book.symbol}:orderbook",
            book.model_dump_json(),
            self.latest_ttl_seconds,
        )

    async def append_trade(self, trade: MarketTrade, maximum: int = 100) -> None:
        if not self.available:
            return
        key = f"market:{trade.symbol}:trades"
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.lpush(key, trade.model_dump_json())
                pipe.ltrim(key, 0, maximum - 1)
                pipe.expire(key, self.latest_ttl_seconds)
                await pipe.execute()
        except RedisError as exc:
            self._disable("trade_write", exc)

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except RedisError:
            return False

    async def _get(self, key: str) -> str | bytes | None:
        if not self.available:
            return None
        try:
            return await self.redis.get(key)
        except RedisError as exc:
            self._disable("read", exc)
            return None

    async def _set(self, key: str, value: str, ttl_seconds: int) -> None:
        if not self.available:
            return
        try:
            await self.redis.setex(key, ttl_seconds, value)
        except RedisError as exc:
            self._disable("write", exc)

    def _disable(self, operation: str, exc: Exception) -> None:
        self.available = False
        structlog.get_logger().warning(
            "MARKET_CACHE_UNAVAILABLE", operation=operation, error=str(exc)
        )
