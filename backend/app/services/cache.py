import json
from typing import Protocol

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.market import Candle


class CandleCache(Protocol):
    async def get(self, key: str) -> list[Candle] | None: ...
    async def set(self, key: str, candles: list[Candle], ttl_seconds: int) -> None: ...


class RedisCandleCache:
    """Best-effort cache: Redis failures never manufacture or block market data."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._available = True

    async def get(self, key: str) -> list[Candle] | None:
        if not self._available:
            return None
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None
            return [Candle.model_validate(item) for item in json.loads(raw)]
        except (RedisError, ValueError, TypeError) as exc:
            self._available = False
            structlog.get_logger().warning("candle_cache_read_failed", error=str(exc))
            return None

    async def set(self, key: str, candles: list[Candle], ttl_seconds: int) -> None:
        if not self._available:
            return
        try:
            payload = json.dumps([item.model_dump(mode="json") for item in candles])
            await self.redis.setex(key, ttl_seconds, payload)
        except (RedisError, ValueError, TypeError) as exc:
            self._available = False
            structlog.get_logger().warning("candle_cache_write_failed", error=str(exc))
