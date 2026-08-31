import asyncio
from datetime import UTC, datetime

from app.domain.market import Timeframe
from app.services.coindcx.public_client import CoinDCXPublicClient

from .cache import RedisMarketDataStore
from .candles import HistoricalCandleService
from .discovery import MarketDiscoveryService
from .models import CandleResult, Market, MultiTimeframeResult, Ticker
from .normalization import epoch_milliseconds


class MarketDataService:
    def __init__(
        self,
        client: CoinDCXPublicClient,
        candle_service: HistoricalCandleService,
        *,
        cache: RedisMarketDataStore | None = None,
    ) -> None:
        self.client = client
        self.discovery = MarketDiscoveryService(client)
        self.candles = candle_service
        self.cache = cache
        self.last_market_update: datetime | None = None

    async def get_markets(
        self, *, include_details: bool = False, limit: int | None = None
    ) -> tuple[list[Market], dict[str, str]]:
        markets, errors = await self.discovery.get_eligible_markets(
            include_details=include_details, limit=limit
        )
        self.last_market_update = datetime.now(UTC)
        return markets, errors

    async def get_candles(self, symbol: str, timeframe: Timeframe, limit: int) -> CandleResult:
        result = await self.candles.get_candles(symbol, timeframe, limit)
        if result.candles:
            self.last_market_update = result.candles[-1].timestamp
        return result

    async def get_latest_candle(self, symbol: str, timeframe: Timeframe):
        return await self.candles.get_latest_candle(symbol, timeframe)

    async def get_multi_timeframe_candles(
        self, symbol: str, timeframes: list[Timeframe], limit: int
    ) -> MultiTimeframeResult:
        calls = [self.get_candles(symbol, timeframe, limit) for timeframe in timeframes]
        outcomes = await asyncio.gather(*calls, return_exceptions=True)
        results, errors = {}, {}
        for timeframe, outcome in zip(timeframes, outcomes, strict=True):
            if isinstance(outcome, Exception):
                errors[timeframe] = str(outcome)
            else:
                results[timeframe] = outcome
        return MultiTimeframeResult(symbol=symbol, results=results, errors=errors)

    async def get_ticker(self, symbol: str) -> Ticker | None:
        if self.cache and (ticker := await self.cache.get_ticker(symbol)):
            return ticker
        snapshot = await self.client.current_prices()
        values = snapshot.prices.get(symbol)
        if not values:
            return None
        ticker = Ticker(
            symbol=symbol,
            timestamp=epoch_milliseconds(snapshot.ts),
            last_price=values.get("ls"),
            mark_price=values.get("mp"),
            high_24h=values.get("h"),
            low_24h=values.get("l"),
            volume_24h=values.get("v"),
            price_change_percent=values.get("pc"),
        )
        if self.cache:
            await self.cache.set_ticker(ticker)
        self.last_market_update = ticker.timestamp
        return ticker
