import asyncio
from typing import Protocol

import structlog

from app.domain.market import Instrument
from app.services.coindcx.models import CoinDCXInstrument

from .models import Market, MarketType
from .normalization import normalize_active_symbol, normalize_market


class DiscoveryClient(Protocol):
    async def active_instruments(self) -> list[str]: ...
    async def instrument(self, pair: str) -> CoinDCXInstrument: ...


class EligibilityFilter:
    def eligible(self, market: Market) -> bool:
        return (
            market.market_type == MarketType.FUTURES
            and market.quote_asset == "USDT"
            and market.status == "active"
        )


class MarketDiscoveryService:
    def __init__(self, client: DiscoveryClient, concurrency: int = 8) -> None:
        self.client = client
        self.filter = EligibilityFilter()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def get_eligible_markets(
        self, *, include_details: bool = False, limit: int | None = None
    ) -> tuple[list[Market], dict[str, str]]:
        symbols = await self.client.active_instruments()
        if limit is not None:
            symbols = symbols[:limit]
        if not include_details:
            markets, errors = [], {}
            for symbol in symbols:
                try:
                    market = normalize_active_symbol(symbol)
                    if self.filter.eligible(market):
                        markets.append(market)
                except ValueError as exc:
                    errors[symbol] = str(exc)
            structlog.get_logger().info(
                "MARKET_DISCOVERY", count=len(markets), errors=len(errors), detailed=False
            )
            return markets, errors

        async def fetch(symbol: str):
            async with self._semaphore:
                try:
                    return normalize_market(await self.client.instrument(symbol))
                except Exception as exc:  # noqa: BLE001 - one symbol must not abort discovery
                    return symbol, str(exc)

        results = await asyncio.gather(*(fetch(symbol) for symbol in symbols))
        markets = [
            item for item in results if isinstance(item, Market) and self.filter.eligible(item)
        ]
        errors = {item[0]: item[1] for item in results if isinstance(item, tuple)}
        structlog.get_logger().info(
            "MARKET_DISCOVERY", count=len(markets), errors=len(errors), detailed=True
        )
        return sorted(markets, key=lambda item: item.symbol), errors

    async def discover_usdt_futures(
        self, *, load_details: bool = False, limit: int | None = None
    ) -> list[Instrument]:
        """Phase 1 compatibility boundary for the existing scanner."""
        markets, _ = await self.get_eligible_markets(include_details=load_details, limit=limit)
        return [
            Instrument(
                pair=item.symbol,
                status=item.status,
                margin_currency="USDT",
                quote_currency=item.quote_asset,
                underlying_currency=item.base_asset,
                min_quantity=item.min_quantity,
                quantity_precision=item.quantity_precision,
                quantity_increment=item.step_size,
                price_increment=item.tick_size,
                min_notional=item.min_notional,
            )
            for item in markets
        ]
