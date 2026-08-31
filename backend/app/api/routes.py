from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.clients.coindcx import CoinDCXPublicClient
from app.config import Settings, get_settings
from app.db.session import get_session
from app.domain.market import Timeframe
from app.indicators import IndicatorEngine
from app.market_data.candles import HistoricalCandleService
from app.market_data.discovery import MarketDiscoveryService
from app.market_data.repository import CandleRepository
from app.market_data.runtime import MarketDataRuntime
from app.market_data.service import MarketDataService
from app.scanner.engine import MarketScanner
from app.scoring.engine import OpportunityScorer
from app.services.cache import RedisCandleCache
from app.services.candles import CandleService
from app.services.coindcx.public_client import CoinDCXPublicClient as MarketDataClient

router = APIRouter(prefix="/api/v1")
SettingsDependency = Annotated[Settings, Depends(get_settings)]
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def create_market_data_client(settings: Settings) -> MarketDataClient:
    return MarketDataClient(
        settings.coindcx_api_base_url,
        settings.coindcx_public_base_url,
        settings.request_timeout_seconds,
        requests_per_second=settings.coindcx_requests_per_second,
        max_retries=settings.coindcx_max_retries,
    )


def runtime_from(request: Request) -> MarketDataRuntime:
    return request.app.state.market_data_runtime


@router.get("/health")
async def health(settings: SettingsDependency) -> dict:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "live_execution_available": False,
        "phase": 2,
    }


@router.get("/markets")
async def markets(
    request: Request,
    settings: SettingsDependency,
    details: bool = False,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> dict:
    async with create_market_data_client(settings) as client:
        service = MarketDataService(
            client,
            HistoricalCandleService(client),
            cache=runtime_from(request).store,
        )
        items, errors = await service.get_markets(include_details=details, limit=limit)
        runtime_from(request).record_update(service.last_market_update)
        return {
            "count": len(items),
            "items": [item.model_dump(mode="json") for item in items],
            "errors": errors,
            "detailed": details,
        }


@router.get("/markets/{symbol}/candles")
async def market_candles(
    symbol: str,
    request: Request,
    settings: SettingsDependency,
    session: SessionDependency,
    timeframe: Timeframe,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict:
    async with create_market_data_client(settings) as client:
        service = MarketDataService(
            client,
            HistoricalCandleService(
                client,
                cache=runtime_from(request).store,
                repository=CandleRepository(session),
                cache_ttl_seconds=settings.candle_cache_ttl_seconds,
            ),
            cache=runtime_from(request).store,
        )
        result = await service.get_candles(symbol, timeframe, limit)
        runtime_from(request).record_update(service.last_market_update)
        return result.model_dump(mode="json")


@router.get("/markets/{symbol}/multi-timeframe")
async def market_multi_timeframe(
    symbol: str,
    request: Request,
    settings: SettingsDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict:
    async with create_market_data_client(settings) as client:
        service = MarketDataService(
            client,
            HistoricalCandleService(
                client,
                cache=runtime_from(request).store,
                repository=CandleRepository(session),
                cache_ttl_seconds=settings.candle_cache_ttl_seconds,
            ),
            cache=runtime_from(request).store,
        )
        result = await service.get_multi_timeframe_candles(symbol, list(Timeframe), limit)
        runtime_from(request).record_update(service.last_market_update)
        return result.model_dump(mode="json")


@router.get("/markets/{symbol}/ticker")
async def market_ticker(symbol: str, request: Request, settings: SettingsDependency) -> dict:
    async with create_market_data_client(settings) as client:
        service = MarketDataService(
            client,
            HistoricalCandleService(client),
            cache=runtime_from(request).store,
        )
        ticker = await service.get_ticker(symbol)
        runtime_from(request).record_update(service.last_market_update)
        return {"ticker": None if ticker is None else ticker.model_dump(mode="json")}


@router.get("/health/market-data")
async def market_data_health(
    request: Request, settings: SettingsDependency, session: SessionDependency
) -> dict:
    runtime = runtime_from(request)
    try:
        async with create_market_data_client(settings) as client:
            snapshot = await client.current_prices()
            runtime.rest_healthy = True
            runtime.record_update(datetime.fromtimestamp(float(snapshot.ts) / 1000, tz=UTC))
    except Exception:  # noqa: BLE001 - health probes must report, never crash
        runtime.rest_healthy = False
    redis_healthy = await runtime.store.ping()
    try:
        await session.execute(text("SELECT 1"))
        database_healthy = True
    except Exception:  # noqa: BLE001 - health probes must report, never crash
        database_healthy = False
    websocket = runtime.websocket.health()
    latest = runtime.last_market_update or runtime.websocket.last_message_at
    stale = (
        latest is None
        or (datetime.now(UTC) - latest).total_seconds() > settings.coindcx_websocket_stale_seconds
    )
    return {
        "rest": "healthy" if runtime.rest_healthy else "unhealthy",
        "websocket": websocket["status"],
        "redis": "healthy" if redis_healthy else "unhealthy",
        "database": "healthy" if database_healthy else "unhealthy",
        "last_market_update": latest,
        "stale": stale,
        "subscriptions": websocket["subscriptions"],
    }


@router.post("/scanner/run")
async def run_scanner(
    settings: SettingsDependency, limit: Annotated[int, Query(ge=1, le=100)] = 25
) -> dict:
    async with CoinDCXPublicClient(
        settings.coindcx_api_base_url,
        settings.coindcx_public_base_url,
        settings.request_timeout_seconds,
    ) as client:
        instruments = await MarketDiscoveryService(client).discover_usdt_futures(
            load_details=True, limit=limit
        )
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        candle_service = CandleService(
            client, RedisCandleCache(redis), settings.candle_cache_ttl_seconds
        )
        scanner = MarketScanner(
            client,
            candle_service,
            MultiTimeframeAnalyzer(IndicatorEngine(), settings.scanner.relative_volume_lookback),
            OpportunityScorer(settings.score_weights),
            settings.scanner,
        )
        try:
            opportunities, rejected = await scanner.scan(instruments)
            return {
                "mode": settings.trading_mode,
                "scanned": len(instruments),
                "opportunities": [item.model_dump() for item in opportunities],
                "rejected": rejected,
            }
        finally:
            await redis.aclose()
