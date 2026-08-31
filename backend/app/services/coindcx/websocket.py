import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import socketio
import structlog

from app.domain.market import Timeframe
from app.market_data.cache import RedisMarketDataStore
from app.market_data.normalization import (
    normalize_tickers,
    normalize_websocket_candle,
    normalize_websocket_orderbook,
    normalize_websocket_trade,
)

from .constants import (
    CURRENT_PRICES_CHANNEL,
    CURRENT_PRICES_EVENT,
    ORDERBOOK_DEPTHS,
    WEBSOCKET_CANDLE_INTERVALS,
)


class WebSocketStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"
    STOPPED = "stopped"


class CoinDCXWebSocketClient:
    """Public futures Socket.IO client. No authentication or private channels."""

    def __init__(
        self,
        url: str,
        *,
        store: RedisMarketDataStore | None = None,
        stale_after_seconds: int = 45,
        socket: Any | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.url = url
        self.store = store
        self.stale_after_seconds = stale_after_seconds
        self.socket = socket or socketio.AsyncClient(reconnection=False, logger=False)
        self._sleep = sleeper
        self.status = WebSocketStatus.DISCONNECTED
        self.last_message_at: datetime | None = None
        self._desired_channels: set[str] = set()
        self._joined_channels: set[str] = set()
        self._orderbook_symbols: set[str] = set()
        self._stop = False
        self.log = structlog.get_logger()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.socket.on("connect", handler=self._on_connect)
        self.socket.on("disconnect", handler=self._on_disconnect)
        self.socket.on(CURRENT_PRICES_EVENT, handler=self._on_current_prices)
        self.socket.on("candlestick", handler=self._on_candlestick)
        self.socket.on("new-trade", handler=self._on_trade)
        self.socket.on("depth-snapshot", handler=self._on_orderbook)

    async def subscribe_current_prices(self) -> None:
        await self._subscribe(CURRENT_PRICES_CHANNEL)

    async def subscribe_candles(self, symbol: str, timeframe: Timeframe) -> None:
        interval = timeframe.value
        if interval not in WEBSOCKET_CANDLE_INTERVALS:
            raise ValueError(f"unsupported documented WebSocket candle interval: {interval}")
        await self._subscribe(f"{symbol}_{interval}-futures")

    async def subscribe_trades(self, symbol: str) -> None:
        await self._subscribe(f"{symbol}@trades-futures")

    async def subscribe_orderbook(self, symbol: str, depth: int = 20) -> None:
        if depth not in ORDERBOOK_DEPTHS:
            raise ValueError("documented futures order-book depth must be 10, 20, or 50")
        self._orderbook_symbols.add(symbol)
        await self._subscribe(f"{symbol}@orderbook@{depth}-futures")

    async def _subscribe(self, channel: str) -> None:
        if channel in self._desired_channels:
            return
        self._desired_channels.add(channel)
        if self.status == WebSocketStatus.CONNECTED:
            await self._join(channel)

    async def _join(self, channel: str) -> None:
        if channel in self._joined_channels:
            return
        await self.socket.emit("join", {"channelName": channel})
        self._joined_channels.add(channel)

    async def connect(self) -> None:
        if self.status in {WebSocketStatus.CONNECTING, WebSocketStatus.CONNECTED}:
            return
        self.status = WebSocketStatus.CONNECTING
        self.log.info("COINDCX_CONNECTION", transport="socketio", state="connecting")
        await self.socket.connect(self.url, transports=["websocket"], wait_timeout=10)
        if self.status == WebSocketStatus.CONNECTING:
            await self._on_connect()

    async def run_forever(self) -> None:
        self._stop = False
        attempt = 0
        monitor = asyncio.create_task(self._stale_monitor())
        try:
            while not self._stop:
                try:
                    await self.connect()
                    attempt = 0
                    await self.socket.wait()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - reconnect after transport failures
                    self.status = WebSocketStatus.DISCONNECTED
                    self.log.warning("COINDCX_WEBSOCKET_DISCONNECTED", error=str(exc))
                if self._stop:
                    break
                delay = min(1 * (2**attempt), 30)
                attempt += 1
                self.log.info("COINDCX_RECONNECT", attempt=attempt, delay_seconds=delay)
                await self._sleep(delay)
        finally:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            if getattr(self.socket, "connected", False):
                await self.socket.disconnect()
            self.status = WebSocketStatus.STOPPED

    async def shutdown(self) -> None:
        self._stop = True
        if getattr(self.socket, "connected", False):
            await self.socket.disconnect()
        self.status = WebSocketStatus.STOPPED

    async def _on_connect(self) -> None:
        self.status = WebSocketStatus.CONNECTED
        self.last_message_at = datetime.now(UTC)
        self._joined_channels.clear()
        for channel in sorted(self._desired_channels):
            await self._join(channel)
        self.log.info("COINDCX_WEBSOCKET_CONNECTED", subscriptions=len(self._joined_channels))

    async def _on_disconnect(self, *_: Any) -> None:
        self._joined_channels.clear()
        if not self._stop:
            self.status = WebSocketStatus.DISCONNECTED
        self.log.info("COINDCX_WEBSOCKET_DISCONNECTED")

    async def _on_current_prices(self, payload: dict) -> None:
        await self._handle("ticker", payload, self._store_tickers)

    async def _on_candlestick(self, payload: dict) -> None:
        await self._handle("candlestick", payload, self._store_candle)

    async def _on_trade(self, payload: dict) -> None:
        await self._handle("trade", payload, self._store_trade)

    async def _on_orderbook(self, payload: dict) -> None:
        async def store(payload_: dict) -> None:
            data = payload_.get("data", payload_)
            symbol = data.get("s") if isinstance(data, dict) else None
            if not symbol and len(self._orderbook_symbols) == 1:
                symbol = next(iter(self._orderbook_symbols))
            if not symbol:
                raise ValueError("order-book message has no unambiguous symbol")
            book = normalize_websocket_orderbook(symbol, payload_)
            if self.store:
                await self.store.set_orderbook(book)

        await self._handle("orderbook", payload, store)

    async def _handle(
        self, kind: str, payload: dict, handler: Callable[[dict], Awaitable[None]]
    ) -> None:
        try:
            await handler(payload)
            self.last_message_at = datetime.now(UTC)
            if self.status == WebSocketStatus.STALE:
                self.status = WebSocketStatus.CONNECTED
        except Exception as exc:  # noqa: BLE001 - malformed events are isolated by design
            self.log.warning("COINDCX_WEBSOCKET_MESSAGE_ERROR", kind=kind, error=str(exc))

    async def _store_tickers(self, payload: dict) -> None:
        tickers = normalize_tickers(payload)
        if self.store:
            for ticker in tickers:
                await self.store.set_ticker(ticker)

    async def _store_candle(self, payload: dict) -> None:
        candle = normalize_websocket_candle(payload)
        if self.store:
            await self.store.set_latest_candle(candle)

    async def _store_trade(self, payload: dict) -> None:
        trade = normalize_websocket_trade(payload)
        if self.store:
            await self.store.append_trade(trade)

    async def _stale_monitor(self) -> None:
        interval = max(1, self.stale_after_seconds / 3)
        while not self._stop:
            await self._sleep(interval)
            if (
                self.status == WebSocketStatus.CONNECTED
                and self.last_message_at
                and (datetime.now(UTC) - self.last_message_at).total_seconds()
                > self.stale_after_seconds
            ):
                self.status = WebSocketStatus.STALE
                self.log.warning("COINDCX_WEBSOCKET_DISCONNECTED", reason="stale_connection")
                if getattr(self.socket, "connected", False):
                    await self.socket.disconnect()

    def health(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "last_message_at": self.last_message_at,
            "subscriptions": len(self._desired_channels),
            "stale": self.status == WebSocketStatus.STALE,
        }
