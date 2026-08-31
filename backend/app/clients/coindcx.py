"""Backward-compatible Phase 1 adapter. New code imports app.services.coindcx."""

from datetime import UTC, datetime
from typing import Any

from app.domain.market import Candle, Instrument, OrderBook
from app.services.coindcx import CoinDCXError
from app.services.coindcx.public_client import CoinDCXPublicClient as PublicClient


class CoinDCXPublicClient(PublicClient):
    async def get_active_instruments(self) -> list[str]:
        return [pair for pair in await self.active_instruments() if pair.endswith("_USDT")]

    async def get_instrument(self, pair: str) -> Instrument:
        raw = await self.instrument(pair)
        return Instrument(
            pair=raw.pair,
            status=raw.status.lower(),
            margin_currency=raw.settle_currency_short_name,
            quote_currency=raw.quote_currency_short_name,
            underlying_currency=raw.underlying_currency_short_name,
            min_quantity=raw.min_quantity,
            quantity_increment=raw.quantity_increment,
            price_increment=raw.price_increment,
            min_notional=raw.min_notional,
            max_leverage=max(raw.max_leverage_long or 0, raw.max_leverage_short or 0) or None,
        )

    async def get_candles(
        self, pair: str, start_seconds: int, end_seconds: int, resolution: str
    ) -> list[Candle]:
        rows = await self.candlesticks(pair, start_seconds, end_seconds, resolution)
        return sorted(
            (
                Candle(
                    time=datetime.fromtimestamp(float(row.time) / 1000, tz=UTC),
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in rows
            ),
            key=lambda item: item.time,
        )

    async def get_order_book(self, pair: str, depth: int = 20) -> OrderBook:
        raw = await self.orderbook(pair, depth)
        return OrderBook(
            pair=pair,
            timestamp=datetime.fromtimestamp(float(raw.ts) / 1000, tz=UTC),
            bids=sorted(((float(p), float(q)) for p, q in raw.bids.items()), reverse=True),
            asks=sorted((float(p), float(q)) for p, q in raw.asks.items()),
        )

    async def get_recent_trades(self, pair: str) -> list[dict[str, Any]]:
        return [item.model_dump() for item in await self.recent_trades(pair)]


__all__ = ["CoinDCXError", "CoinDCXPublicClient"]
