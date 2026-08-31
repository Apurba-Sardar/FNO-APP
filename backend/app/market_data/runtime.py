import asyncio
from datetime import datetime

from redis.asyncio import Redis

from app.config import Settings
from app.services.coindcx.websocket import CoinDCXWebSocketClient

from .cache import RedisMarketDataStore


class MarketDataRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        self.store = RedisMarketDataStore(self.redis, settings.latest_market_data_ttl_seconds)
        self.websocket = CoinDCXWebSocketClient(
            settings.coindcx_websocket_url,
            store=self.store,
            stale_after_seconds=settings.coindcx_websocket_stale_seconds,
        )
        self.websocket_task: asyncio.Task | None = None
        self.last_market_update: datetime | None = None
        self.rest_healthy: bool | None = None

    async def start(self) -> None:
        if self.settings.coindcx_websocket_enabled:
            await self.websocket.subscribe_current_prices()
            self.websocket_task = asyncio.create_task(
                self.websocket.run_forever(), name="coindcx-public-websocket"
            )

    async def stop(self) -> None:
        await self.websocket.shutdown()
        if self.websocket_task:
            self.websocket_task.cancel()
            await asyncio.gather(self.websocket_task, return_exceptions=True)
        await self.redis.aclose()

    def record_update(self, timestamp: datetime | None) -> None:
        if timestamp and (self.last_market_update is None or timestamp > self.last_market_update):
            self.last_market_update = timestamp
