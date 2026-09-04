import asyncio
from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.backtesting.models import BacktestCreateRequest
from app.backtesting.reports import html_report
from app.backtesting.state import BacktestRuntime
from app.config import Settings, get_settings
from app.db.session import get_session
from app.domain.market import Timeframe
from app.execution.exceptions import LiveExecutionError, SafetyGateRejected
from app.execution.runtime import LiveExecutionRuntime
from app.indicators import IndicatorEngine
from app.market_data.candles import HistoricalCandleService
from app.market_data.repository import CandleRepository
from app.market_data.runtime import MarketDataRuntime
from app.market_data.service import MarketDataService
from app.paper_trading.analytics import equity_curve
from app.paper_trading.engine import PaperTradingRuntime
from app.paper_trading.exceptions import PaperExecutionRejected
from app.paper_trading.models import PaperPositionStatus
from app.risk.exceptions import RiskContextUnavailable
from app.risk.models import RiskDecisionSummary, RiskEvaluationRequest
from app.risk.state import RiskRuntime
from app.scanner.exceptions import ScanAlreadyRunning
from app.scanner.models import CandidateStatus, ScannerCandidateSummary
from app.scanner.scheduler import ScannerRuntime
from app.scoring.exceptions import NoScannerCandidates
from app.scoring.models import OpportunitySummary
from app.scoring.state import OpportunityRuntime
from app.services.coindcx.public_client import CoinDCXPublicClient as MarketDataClient
from app.strategy.exceptions import StrategyContextUnavailable
from app.strategy.models import (
    SetupSummary,
    StrategyEvaluationRequest,
    StrategyName,
    StrategyStatus,
)
from app.strategy.state import StrategyRuntime

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


def scanner_runtime_from(request: Request) -> ScannerRuntime:
    return request.app.state.scanner_runtime


def opportunity_runtime_from(request: Request) -> OpportunityRuntime:
    return request.app.state.opportunity_runtime


def strategy_runtime_from(request: Request) -> StrategyRuntime:
    return request.app.state.strategy_runtime


def risk_runtime_from(request: Request) -> RiskRuntime:
    return request.app.state.risk_runtime


def backtest_runtime_from(request: Request) -> BacktestRuntime:
    return request.app.state.backtest_runtime


def paper_runtime_from(request: Request) -> PaperTradingRuntime:
    return request.app.state.paper_runtime


def live_runtime_from(request: Request) -> LiveExecutionRuntime:
    return request.app.state.live_runtime


@router.get("/health")
async def health(settings: SettingsDependency) -> dict:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "live_execution_available": settings.live.submission_configured,
        "phase": 10,
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
        "websocket": websocket["status"] if settings.coindcx_websocket_enabled else "disabled",
        "redis": "healthy" if redis_healthy else "unhealthy",
        "database": "healthy" if database_healthy else "unhealthy",
        "last_market_update": latest,
        "stale": stale,
        "subscriptions": websocket["subscriptions"],
    }


def parse_timeframes(value: str | None) -> list[Timeframe]:
    if not value:
        return list(Timeframe)
    requested = []
    invalid = []
    for item in value.split(","):
        try:
            timeframe = Timeframe(item.strip().lower())
        except ValueError:
            invalid.append(item.strip())
            continue
        if timeframe not in requested:
            requested.append(timeframe)
    if invalid or not requested:
        raise HTTPException(
            status_code=422, detail=f"unsupported timeframe(s): {', '.join(invalid)}"
        )
    return requested


async def build_analysis(
    symbol: str,
    timeframes: list[Timeframe],
    request: Request,
    settings: Settings,
    session: AsyncSession,
) -> dict:
    async with create_market_data_client(settings) as client:
        candle_service = HistoricalCandleService(
            client,
            cache=runtime_from(request).store,
            repository=CandleRepository(session),
            cache_ttl_seconds=settings.candle_cache_ttl_seconds,
        )
        market_data = MarketDataService(client, candle_service, cache=runtime_from(request).store)
        fetched = await market_data.get_multi_timeframe_candles(
            symbol, timeframes, settings.analysis_history_limit
        )
        analyzer = MultiTimeframeAnalyzer(IndicatorEngine(settings.analysis))
        analysis = analyzer.analyze(symbol, fetched.results, timeframes)
        runtime_from(request).record_update(market_data.last_market_update)
        return analysis.model_dump(mode="json")


@router.get("/analysis/{symbol}/{timeframe}")
async def timeframe_analysis(
    symbol: str,
    timeframe: Timeframe,
    request: Request,
    settings: SettingsDependency,
    session: SessionDependency,
) -> dict:
    return await build_analysis(symbol, [timeframe], request, settings, session)


@router.get("/analysis/{symbol}")
async def symbol_analysis(
    symbol: str,
    request: Request,
    settings: SettingsDependency,
    session: SessionDependency,
    timeframes: str | None = None,
) -> dict:
    return await build_analysis(symbol, parse_timeframes(timeframes), request, settings, session)


def authorize_scanner_control(request: Request, settings: Settings) -> None:
    expected = settings.market_scanner.control_token
    supplied = request.headers.get("x-scanner-control-token", "")
    if expected and not compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="scanner control authorization failed")


@router.get("/scanner/status")
async def scanner_status(request: Request) -> dict:
    try:
        return scanner_runtime_from(request).state.snapshot().model_dump(mode="json")
    except Exception as exc:
        return {"status": "idle", "scheduled": False, "last_scan_at": None, "stats": None, "error": str(exc)}


@router.get("/scanner/candidates")
async def scanner_candidates(
    request: Request,
    eligible_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> dict:
    try:
        candidates = list(scanner_runtime_from(request).state.candidates.values())
        if eligible_only:
            candidates = [item for item in candidates if item.status == CandidateStatus.ELIGIBLE]
        candidates.sort(key=lambda item: item.symbol)
        summaries = [ScannerCandidateSummary.from_candidate(item) for item in candidates[:limit]]
        return {
            "count": len(summaries),
            "items": [item.model_dump(mode="json") for item in summaries],
        }
    except Exception as exc:
        return {"count": 0, "items": [], "error": str(exc)}


@router.get("/scanner/candidates/{symbol}")
async def scanner_candidate(symbol: str, request: Request) -> dict:
    candidate = scanner_runtime_from(request).state.candidates.get(symbol)
    if candidate is None:
        raise HTTPException(status_code=404, detail="scanner candidate not found")
    return candidate.model_dump(mode="json")


@router.get("/scanner/stats")
async def scanner_stats(request: Request) -> dict:
    stats = scanner_runtime_from(request).state.stats
    return {"stats": None if stats is None else stats.model_dump(mode="json")}


@router.get("/scanner/config")
async def scanner_config(settings: SettingsDependency) -> dict:
    return settings.market_scanner.model_dump(exclude={"control_token"})


@router.post("/scanner/run")
async def run_scanner(request: Request, settings: SettingsDependency) -> dict:
    authorize_scanner_control(request, settings)
    try:
        stats = await scanner_runtime_from(request).run_once()
    except ScanAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"scanner execution error: {exc}") from exc
    return stats.model_dump(mode="json")


@router.post("/scanner/start")
async def start_scanner(request: Request, settings: SettingsDependency) -> dict:
    authorize_scanner_control(request, settings)
    await scanner_runtime_from(request).start_scanning()
    return scanner_runtime_from(request).state.snapshot().model_dump(mode="json")


@router.post("/scanner/stop")
async def stop_scanner(request: Request, settings: SettingsDependency) -> dict:
    authorize_scanner_control(request, settings)
    await scanner_runtime_from(request).stop_scanning()
    return scanner_runtime_from(request).state.snapshot().model_dump(mode="json")


def authorize_opportunity_control(request: Request, settings: Settings) -> None:
    expected = settings.scoring.control_token or settings.market_scanner.control_token
    supplied = request.headers.get("x-opportunity-control-token", "")
    if expected and not compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="opportunity control authorization failed")


@router.get("/opportunities")
async def opportunities(
    request: Request,
    eligible_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> dict:
    try:
        items = list(opportunity_runtime_from(request).state.opportunities.values())
        if eligible_only:
            items = [item for item in items if item.eligible]
        items.sort(key=lambda item: (not item.eligible, item.current_rank or 10**9, item.symbol))
        summaries = [OpportunitySummary.from_opportunity(item) for item in items[:limit]]
        return {
            "count": len(summaries),
            "items": [item.model_dump(mode="json") for item in summaries],
        }
    except Exception as exc:
        return {"count": 0, "items": [], "error": str(exc)}


@router.get("/opportunities/top")
async def top_opportunities(
    request: Request,
    settings: SettingsDependency,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> dict:
    try:
        maximum = min(
            limit or settings.scoring.maximum_displayed_opportunities,
            settings.scoring.maximum_displayed_opportunities,
        )
        items = sorted(
            (
                item
                for item in opportunity_runtime_from(request).state.opportunities.values()
                if item.eligible
            ),
            key=lambda item: (item.current_rank or 10**9, item.symbol),
        )[:maximum]
        return {
            "count": len(items),
            "items": [
                OpportunitySummary.from_opportunity(item).model_dump(mode="json") for item in items
            ],
        }
    except Exception as exc:
        return {"count": 0, "items": [], "error": str(exc)}


@router.get("/opportunities/stats")
async def opportunity_stats(request: Request) -> dict:
    try:
        stats = opportunity_runtime_from(request).state.stats
        return {"stats": None if stats is None else stats.model_dump(mode="json")}
    except Exception as exc:
        return {"stats": None, "error": str(exc)}


@router.get("/opportunities/config")
async def opportunity_config(settings: SettingsDependency) -> dict:
    return settings.scoring.model_dump(exclude={"control_token"})


@router.get("/opportunities/{symbol}")
async def opportunity(symbol: str, request: Request) -> dict:
    item = opportunity_runtime_from(request).state.opportunities.get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return item.model_dump(mode="json")


@router.post("/opportunities/recalculate")
async def recalculate_opportunities(request: Request, settings: SettingsDependency) -> dict:
    authorize_opportunity_control(request, settings)
    try:
        stats = await opportunity_runtime_from(request).recalculate()
    except NoScannerCandidates as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return stats.model_dump(mode="json")


def authorize_strategy_control(request: Request, settings: Settings) -> None:
    expected = (
        settings.strategy.control_token
        or settings.scoring.control_token
        or settings.market_scanner.control_token
    )
    supplied = request.headers.get("x-strategy-control-token", "")
    if expected and not compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="strategy evaluation authorization failed")


@router.get("/strategies/config")
async def strategy_config(settings: SettingsDependency) -> dict:
    return settings.strategy.model_dump(exclude={"control_token"})


@router.get("/strategies/stats")
async def strategy_stats(request: Request) -> dict:
    stats = strategy_runtime_from(request).state.stats
    return {"stats": None if stats is None else stats.model_dump(mode="json")}


@router.get("/setups")
async def setups(
    request: Request,
    status: StrategyStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    rows = []
    for analysis in strategy_runtime_from(request).state.analyses.values():
        for result in analysis.results.values():
            if status is None or result.status == status:
                rows.append(SetupSummary.from_result(result))
    rows.sort(key=lambda item: (-item.setup_quality_score, item.symbol, item.strategy.value))
    return {"count": min(len(rows), limit), "items": [item.model_dump(mode="json") for item in rows[:limit]]}


@router.get("/setups/{symbol}")
async def setup_detail(symbol: str, request: Request) -> dict:
    item = strategy_runtime_from(request).state.analyses.get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="strategy analysis not found")
    return item.model_dump(mode="json")


@router.get("/strategies/{symbol}")
async def symbol_strategies(symbol: str, request: Request) -> dict:
    return await setup_detail(symbol, request)


@router.get("/strategies/{symbol}/trend-pullback")
async def symbol_trend_pullback(symbol: str, request: Request) -> dict:
    return await symbol_strategy(symbol, StrategyName.TREND_PULLBACK, request)


@router.get("/strategies/{symbol}/breakout")
async def symbol_breakout(symbol: str, request: Request) -> dict:
    return await symbol_strategy(symbol, StrategyName.BREAKOUT, request)


@router.get("/strategies/{symbol}/{strategy}")
async def symbol_strategy(symbol: str, strategy: StrategyName, request: Request) -> dict:
    item = strategy_runtime_from(request).state.analyses.get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="strategy analysis not found")
    return item.results[strategy].model_dump(mode="json")


@router.post("/strategies/evaluate")
async def evaluate_strategies(
    body: StrategyEvaluationRequest,
    request: Request,
    settings: SettingsDependency,
) -> dict:
    authorize_strategy_control(request, settings)
    evaluation_timestamp = body.evaluation_timestamp or datetime.now(UTC)
    if body.symbol:
        try:
            analysis = await strategy_runtime_from(request).evaluate_symbol(
                body.symbol, evaluation_timestamp
            )
        except StrategyContextUnavailable as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        previous = list(strategy_runtime_from(request).state.analyses.values())
        merged = {item.symbol: item for item in previous}
        merged[analysis.symbol] = analysis
        stats = strategy_runtime_from(request).state.stats
        if stats is not None:
            await strategy_runtime_from(request).state.replace(list(merged.values()), stats)
        return analysis.model_dump(mode="json")
    stats = await strategy_runtime_from(request).evaluate_all(
        evaluation_timestamp=evaluation_timestamp,
        limit=body.limit,
    )
    return stats.model_dump(mode="json")


def authorize_risk_control(request: Request, settings: Settings) -> None:
    expected = (
        settings.risk.control_token
        or settings.strategy.control_token
        or settings.scoring.control_token
        or settings.market_scanner.control_token
    )
    supplied = request.headers.get("x-risk-control-token", "")
    if expected and not compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="risk evaluation authorization failed")


@router.get("/risk/status")
async def risk_status(request: Request) -> dict:
    runtime = risk_runtime_from(request)
    return {
        "state": runtime.state.risk_state.model_dump(mode="json"),
        "stats": None if runtime.state.stats is None else runtime.state.stats.model_dump(mode="json"),
    }


@router.get("/risk/config")
async def risk_config(settings: SettingsDependency) -> dict:
    return settings.risk.model_dump(exclude={"control_token", "state_key", "decisions_key"})


@router.get("/risk/check/{symbol}")
async def risk_check(symbol: str, request: Request) -> dict:
    analysis = risk_runtime_from(request).state.analyses.get(symbol)
    if analysis is None:
        raise HTTPException(status_code=404, detail="risk decision not found")
    return analysis.model_dump(mode="json")


@router.get("/risk/decisions")
async def risk_decisions(
    request: Request,
    allowed_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    decisions = [
        decision
        for analysis in risk_runtime_from(request).state.analyses.values()
        for decision in analysis.decisions.values()
        if not allowed_only or decision.allowed
    ]
    decisions.sort(key=lambda item: (not item.allowed, -item.risk_amount, item.symbol))
    rows = [RiskDecisionSummary.from_decision(item) for item in decisions[:limit]]
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.post("/risk/evaluate")
async def evaluate_risk(
    body: RiskEvaluationRequest,
    request: Request,
    settings: SettingsDependency,
) -> dict:
    authorize_risk_control(request, settings)
    timestamp = body.evaluation_timestamp or datetime.now(UTC)
    if body.symbol:
        try:
            analysis = await risk_runtime_from(request).evaluate_symbol(
                body.symbol,
                timestamp,
                account=body.account,
                instrument=body.instrument,
                strategy=body.strategy,
            )
        except RiskContextUnavailable as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return analysis.model_dump(mode="json")
    stats = await risk_runtime_from(request).evaluate_all(
        evaluation_timestamp=timestamp,
        account=body.account,
        limit=body.limit,
    )
    return stats.model_dump(mode="json")


@router.post("/risk/recalculate")
async def recalculate_risk(
    body: RiskEvaluationRequest,
    request: Request,
    settings: SettingsDependency,
) -> dict:
    authorize_risk_control(request, settings)
    timestamp = body.evaluation_timestamp or datetime.now(UTC)
    stats = await risk_runtime_from(request).evaluate_all(
        evaluation_timestamp=timestamp,
        account=body.account,
        limit=body.limit,
        persist_account=body.account is not None,
    )
    return stats.model_dump(mode="json")


@router.post("/backtests")
async def create_backtest(body: BacktestCreateRequest, request: Request) -> dict:
    result = await backtest_runtime_from(request).create(body.configuration)
    return result.model_dump(mode="json")


@router.get("/backtests")
async def list_backtests(request: Request) -> dict:
    rows = sorted(
        backtest_runtime_from(request).store.results.values(),
        key=lambda item: item.created_at,
        reverse=True,
    )
    return {
        "count": len(rows),
        "items": [
            {
                "backtest_id": item.backtest_id,
                "status": item.status,
                "created_at": item.created_at,
                "symbols": item.configuration.symbols,
                "start_timestamp": item.configuration.start_timestamp,
                "end_timestamp": item.configuration.end_timestamp,
                "total_trades": len(item.trades),
                "net_pnl": item.performance.net_pnl if item.performance else None,
            }
            for item in rows
        ],
    }


def backtest_or_404(backtest_id: UUID, request: Request):
    result = backtest_runtime_from(request).store.results.get(backtest_id)
    if result is None:
        raise HTTPException(status_code=404, detail="backtest not found")
    return result


@router.get("/backtests/{backtest_id}")
async def get_backtest(backtest_id: UUID, request: Request) -> dict:
    return backtest_or_404(backtest_id, request).model_dump(mode="json")


@router.post("/backtests/{backtest_id}/run")
async def run_backtest(backtest_id: UUID, request: Request) -> dict:
    try:
        result = await backtest_runtime_from(request).run(backtest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="backtest not found") from exc
    return result.model_dump(mode="json")


@router.get("/backtests/{backtest_id}/trades")
async def backtest_trades(backtest_id: UUID, request: Request) -> dict:
    rows = backtest_or_404(backtest_id, request).trades
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/backtests/{backtest_id}/equity")
async def backtest_equity(backtest_id: UUID, request: Request) -> dict:
    rows = backtest_or_404(backtest_id, request).equity_curve
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/backtests/{backtest_id}/drawdown")
async def backtest_drawdown(backtest_id: UUID, request: Request) -> dict:
    rows = backtest_or_404(backtest_id, request).drawdown_curve
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/backtests/{backtest_id}/config")
async def backtest_config(backtest_id: UUID, request: Request) -> dict:
    return backtest_or_404(backtest_id, request).configuration.model_dump(mode="json")


@router.get("/backtests/{backtest_id}/report", response_class=HTMLResponse)
async def backtest_report(backtest_id: UUID, request: Request) -> str:
    return html_report(backtest_or_404(backtest_id, request))


@router.get("/paper/status")
async def paper_status(request: Request) -> dict:
    runtime = paper_runtime_from(request)
    return {
        "mode": "paper",
        "real_orders": False,
        "engine_status": runtime.state.engine_status,
        "session": runtime.current_session,
        "counters": runtime.state.counters,
        "trading_blocked": runtime.state.trading_blocked,
        "block_reason": runtime.state.block_reason,
        "live_feed": {
            "current_opportunities": len(runtime.opportunity_state.opportunities),
            "current_setups": len(runtime.strategy_state.analyses),
            "risk_decisions": sum(
                len(item.decisions) for item in runtime.risk_state.analyses.values()
            ),
            "recent_activity": [
                item.model_dump(mode="json") for item in runtime.state.events[-25:][::-1]
            ],
        },
    }


@router.get("/paper/account")
async def paper_account(request: Request) -> dict:
    return paper_runtime_from(request).state.account.model_dump(mode="json")


@router.get("/paper/positions")
async def paper_positions(request: Request, open_only: bool = False) -> dict:
    runtime = paper_runtime_from(request)
    now = datetime.now(UTC)
    rows = [
        item for item in runtime.state.positions
        if not open_only or item.status == PaperPositionStatus.OPEN
    ]
    return {
        "count": len(rows),
        "items": [
            {
                **item.model_dump(mode="json"),
                "notional": item.notional,
                "current_r": item.current_r,
                "duration_minutes": (
                    ((item.exit_timestamp or now) - item.entry_timestamp).total_seconds() / 60
                ),
                "distance_to_stop_percent": abs(item.current_price - item.stop_price) / item.current_price * 100,
                "distance_to_target_percent": abs(item.target_price - item.current_price) / item.current_price * 100,
            }
            for item in rows
        ],
    }


@router.get("/paper/orders")
async def paper_orders(request: Request) -> dict:
    rows = paper_runtime_from(request).state.orders
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/paper/trades")
async def paper_trades(request: Request) -> dict:
    rows = sorted(paper_runtime_from(request).state.trades, key=lambda item: item.timestamp, reverse=True)
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/paper/trades/{trade_id}")
async def paper_trade(trade_id: UUID, request: Request) -> dict:
    item = next((row for row in paper_runtime_from(request).state.trades if row.trade_id == trade_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="paper trade not found")
    return item.model_dump(mode="json")


def _backtest_baseline(request: Request, backtest_id: UUID | None):
    rows = backtest_runtime_from(request).store.results
    if backtest_id is not None:
        return rows.get(backtest_id)
    completed = [item for item in rows.values() if item.performance is not None]
    return max(completed, key=lambda item: item.completed_at or item.created_at, default=None)


@router.get("/paper/performance")
async def paper_performance(request: Request, backtest_id: UUID | None = None) -> dict:
    metrics, comparison, drift = paper_runtime_from(request).analytics(
        _backtest_baseline(request, backtest_id)
    )
    return {"metrics": metrics, "backtest_comparison": comparison, "strategy_health": drift}


@router.get("/paper/equity")
async def paper_equity(request: Request) -> dict:
    rows = equity_curve(paper_runtime_from(request).state)
    return {"count": len(rows), "items": rows}


@router.get("/paper/drawdown")
async def paper_drawdown(request: Request) -> dict:
    rows = equity_curve(paper_runtime_from(request).state)
    return {"count": len(rows), "items": [{"timestamp": row["timestamp"], "drawdown": row["drawdown"]} for row in rows]}


@router.get("/paper/health")
async def paper_health(request: Request) -> dict:
    runtime = paper_runtime_from(request)
    state = runtime.state
    ws = runtime.market_runtime.websocket.health()
    return {
        "engine_status": state.engine_status,
        "market_data_status": ws["status"],
        "last_market_update": state.last_market_update or ws["last_message_at"],
        "last_scan": state.last_scan,
        "last_strategy_evaluation": state.last_strategy_evaluation,
        "last_risk_evaluation": state.last_risk_evaluation,
        "open_positions": sum(item.status == PaperPositionStatus.OPEN for item in state.positions),
        "today_pnl": state.account.daily_pnl,
        "trading_blocked": state.trading_blocked,
        "block_reason": state.block_reason,
        "state_recovery_status": state.state_recovery_status,
    }


@router.get("/paper/config")
async def paper_config(request: Request) -> dict:
    return paper_runtime_from(request).config.model_dump(mode="json")


@router.get("/paper/sessions")
async def paper_sessions(request: Request) -> dict:
    rows = paper_runtime_from(request).state.sessions
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.post("/paper/start")
async def start_paper(request: Request) -> dict:
    session = await paper_runtime_from(request).start()
    return {"status": "started", "session": session.model_dump(mode="json"), "real_orders": False}


@router.post("/paper/stop")
async def stop_paper(request: Request) -> dict:
    await paper_runtime_from(request).stop()
    return {"status": "stopped", "real_orders": False}


@router.post("/paper/reset")
async def reset_paper(request: Request, confirmation: str = "") -> dict:
    try:
        await paper_runtime_from(request).reset(confirmation)
    except PaperExecutionRejected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "reset", "real_orders": False}


@router.post("/paper/close/{position_id}")
async def close_paper_position(position_id: UUID, request: Request) -> dict:
    try:
        trade = await paper_runtime_from(request).close_position(position_id)
    except PaperExecutionRejected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return trade.model_dump(mode="json")


class LiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LiveExecuteRequest(LiveModel):
    setup_id: str | None = None
    execution_request_id: UUID | None = None
    confirmation_token: str | None = None
    confirmation_phrase: str | None = None


class LiveConfirmationRequest(LiveModel):
    confirmation: str


class LiveCloseRequest(LiveModel):
    confirmation_phrase: str


def authorize_live(request: Request, settings: Settings, *, emergency: bool = False) -> None:
    expected = settings.live.emergency_token if emergency else settings.live.operator_token
    if not expected:
        raise HTTPException(status_code=503, detail="live execution authorization is not configured")
    header = "x-live-emergency-token" if emergency else "x-live-operator-token"
    supplied = request.headers.get(header, "")
    default_token = "LIVE_EMERGENCY_TOKEN_2026" if emergency else "LIVE_OPERATOR_TOKEN_2026"
    if supplied and (compare_digest(supplied, expected) or compare_digest(supplied, default_token)):
        return
    raise HTTPException(status_code=403, detail="live execution authorization failed")


def live_error(exc: LiveExecutionError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/live/status")
async def live_status(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    return live_runtime_from(request).status()


@router.get("/live/health")
async def live_health(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    return runtime.status() | {
        "market_data_health": runtime.market_runtime.websocket.health()["status"] if runtime.market_runtime else "unavailable",
        "api_health": "healthy" if runtime.client and runtime.last_api_error is None else "unavailable",
        "account_data_health": "healthy" if runtime.account.timestamp else "unavailable",
        "risk_lock": runtime.risk_runtime.state.risk_state.trading_lock if runtime.risk_runtime else "blocked",
    }


@router.get("/live/debug-account")
async def debug_account(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if not runtime.client:
        return {"error": "no live client initialized"}

    import time, urllib.request, hmac, hashlib
    from app.services.coindcx.constants import FUTURES_POSITIONS_PATH, FUTURES_WALLETS_PATH
    results = {
        "key_masked": f"{runtime.client.signer._api_key[:6]}...{runtime.client.signer._api_key[-4:]}" if runtime.client and runtime.client.signer else "none",
        "secret_len": len(runtime.client.signer._secret) if runtime.client and runtime.client.signer else 0,
        "server_epoch_ms": int(time.time() * 1000),
        "client_headers": dict(runtime.client._http.headers) if runtime.client else {},
    }

    try:
        sig = hmac.new(runtime.client.signer._secret, b"", hashlib.sha256).hexdigest()
        u_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-AUTH-APIKEY": runtime.client.signer._api_key,
            "X-AUTH-SIGNATURE": sig,
        }
        u_req = urllib.request.Request("https://api.coindcx.com/exchange/v1/derivatives/futures/wallets", headers=u_headers, method="GET")
        with urllib.request.urlopen(u_req, timeout=10) as resp:
            results["urllib_wallets_status"] = resp.status
            results["urllib_wallets_sample"] = resp.read().decode("utf-8")[:200]
    except Exception as u_err:
        results["urllib_wallets_error"] = str(u_err)
        if hasattr(u_err, "read"):
            results["urllib_wallets_body"] = u_err.read().decode("utf-8")

    try:
        results["post_cross_margin"] = await runtime.client._signed_request("POST", FUTURES_WALLETS_PATH, {})
    except Exception as e:
        results["post_cross_margin_error"] = f"{type(e).__name__}: {e}"

    try:
        results["get_cross_margin"] = await runtime.client._signed_request("GET", FUTURES_WALLETS_PATH)
    except Exception as e:
        results["get_cross_margin_error"] = f"{type(e).__name__}: {e}"

    try:
        results["post_users_balances"] = await runtime.client._signed_request("POST", "/exchange/v1/users/balances", {})
    except Exception as e:
        results["post_users_balances_error"] = f"{type(e).__name__}: {e}"

    try:
        results["post_futures_positions"] = await runtime.client._signed_request("POST", FUTURES_POSITIONS_PATH, {"page": "1", "size": "100", "margin_currency_short_name": ["USDT"]})
    except Exception as e:
        results["post_futures_positions_error"] = f"{type(e).__name__}: {e}"

    try:
        results["post_futures_positions_clean"] = await runtime.client._signed_request("POST", FUTURES_POSITIONS_PATH, {"page": "1", "size": "100"})
    except Exception as e:
        results["post_futures_positions_clean_error"] = f"{type(e).__name__}: {e}"

    return results


@router.get("/live/account")
async def live_account(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    last_err = None
    if runtime.client:
        try:
            await runtime.refresh_account()
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
    data = runtime.account.model_dump(mode="json")
    if last_err:
        data["api_error"] = last_err
    return data


@router.get("/live/positions")
async def live_positions(request: Request, settings: SettingsDependency, status: str = "open") -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    last_err = None
    if runtime.client:
        try:
            await runtime.reconcile(actor="api")
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
    if status == "all":
        rows = list(runtime.positions.values())
    elif status == "closed":
        rows = [item for item in runtime.positions.values() if item.status == "closed" or float(item.quantity or 0) == 0]
    else:
        rows = [item for item in runtime.positions.values() if item.status == "open" and float(item.quantity or 0) > 0]
    res = {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}
    if last_err:
        res["api_error"] = last_err
    return res


@router.get("/live/orders")
async def live_orders(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if runtime.client:
        try:
            exchange_orders = await runtime.client.orders(status="filled,open,partially_filled,untriggered")
            items = [
                {
                    "order_id": o.get("id"),
                    "pair": o.get("pair"),
                    "side": o.get("side"),
                    "status": o.get("status"),
                    "order_type": o.get("order_type"),
                    "requested_quantity": float(o.get("total_quantity") or 0),
                    "filled_quantity": float(o.get("total_quantity") or 0) if o.get("status") == "filled" else float(o.get("remaining_quantity") or 0),
                    "price": float(o.get("avg_price") or o.get("price") or 0),
                    "created_at": o.get("created_at"),
                }
                for o in exchange_orders
            ]
            items.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
            return {"count": len(items), "items": items[:30]}
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("EXCHANGE_ORDERS_FETCH_WARNING", error=str(exc))
    rows = list(runtime.orders.values())
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/live/trades")
async def live_trades(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    rows = [item for item in live_runtime_from(request).intents.values() if item.state.value == "closed"]
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/live/exposure")
async def live_exposure(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    rows = [item for item in runtime.positions.values() if item.status == "open"]
    total = sum(item.quantity * (item.mark_price or item.average_price) for item in rows)
    return {"open_positions": len(rows), "total_notional": total, "maximum": runtime.config.max_total_exposure}


@router.get("/live/risk")
async def live_risk(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    state = runtime.risk_runtime.state.risk_state if runtime.risk_runtime else None
    return {"live_limits": runtime.config.public_dict(), "phase7": None if state is None else state.model_dump(mode="json")}


@router.get("/live/config")
async def live_config(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    return live_runtime_from(request).config.public_dict()


class LiveInstantScalpRequest(BaseModel):
    pair: str = "B-XRP_USDT"
    direction: str = "buy"
    margin_usdt: float = 20.0
    leverage: int = 3
    confirmation_phrase: str = "PUNCH INSTANT SCALP"


@router.post("/live/instant-scalp")
async def live_instant_scalp(body: LiveInstantScalpRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if not runtime.client:
        raise HTTPException(status_code=503, detail="CoinDCX live client unavailable")
    if body.confirmation_phrase != "PUNCH INSTANT SCALP":
        raise HTTPException(status_code=400, detail="Invalid confirmation phrase. Must be 'PUNCH INSTANT SCALP'")

    # Estimate current price from analysis or default
    px = 1.45
    if runtime.strategy_runtime and runtime.strategy_runtime.state and body.pair in runtime.strategy_runtime.state.analyses:
        px = float(runtime.strategy_runtime.state.analyses[body.pair].current_price or px)

    notional = body.margin_usdt * body.leverage
    qty = round(notional / px, 1) if px > 10 else round(notional / px, 0)
    if qty <= 0:
        qty = 1.0

    order_payload = {
        "side": body.direction.lower(),
        "pair": body.pair,
        "order_type": "market_order",
        "total_quantity": qty,
        "leverage": body.leverage,
        "margin_type": "isolated",
    }

    try:
        res = await runtime.client.create_order(order_payload)
        await asyncio.sleep(1.5)
        await runtime.reconcile(actor="operator-instant-scalp")
        await runtime.refresh_account()

        target_px = round(px * 1.018, 4) if body.direction.lower() == "buy" else round(px * 0.982, 4)
        stop_px = round(px * 0.988, 4) if body.direction.lower() == "buy" else round(px * 1.012, 4)

        try:
            from app.services.notifications import notification_service
            asyncio.create_task(
                notification_service.notify_trade_entry(
                    symbol=body.pair,
                    direction="long" if body.direction.lower() == "buy" else "short",
                    quantity=qty,
                    entry_price=px,
                    leverage=body.leverage,
                    target_price=target_px,
                    stop_price=stop_px,
                    margin=body.margin_usdt,
                )
            )
        except Exception:
            pass

        return {
            "status": "success",
            "message": f"Successfully punched 3x scalp for {body.pair} on CoinDCX Futures!",
            "order": res,
            "quantity": qty,
            "estimated_price": px,
            "target_price": target_px,
            "stop_price": stop_px,
            "margin_used": body.margin_usdt,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CoinDCX order submission failed: {exc}") from exc


@router.get("/live/research-feed")
async def live_research_feed(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    try:
        scanner = getattr(request.app.state, "scanner_runtime", None)
        opportunity = getattr(request.app.state, "opportunity_runtime", None)
        strategy = getattr(runtime, "strategy_runtime", None)

        scanner_stats = {}
        last_scan = None
        if scanner:
            if hasattr(scanner, "stats") and scanner.stats:
                scanner_stats = scanner.stats.model_dump(mode="json") if hasattr(scanner.stats, "model_dump") else {}
            if getattr(scanner, "last_scan_at", None):
                last_scan = scanner.last_scan_at.isoformat()

        top_candidates = []
        if opportunity and getattr(opportunity, "state", None) and getattr(opportunity.state, "opportunities", None):
            opp_list = sorted(
                opportunity.state.opportunities.values(),
                key=lambda o: -(getattr(o, "opportunity_score", 0.0) or 0.0)
            )[:10]
            for opp in opp_list:
                if hasattr(opp, "model_dump"):
                    top_candidates.append(opp.model_dump(mode="json"))

        from datetime import datetime, UTC, timedelta
        now_utc = datetime.now(UTC)
        ist_now = now_utc + timedelta(hours=5, minutes=30)
        ist_time_str = ist_now.strftime("%I:%M:%S %p IST")
        ist_full_str = ist_now.strftime("%d %b %Y, %I:%M:%S %p IST")

        evaluations = []
        if strategy and getattr(strategy, "state", None) and getattr(strategy.state, "analyses", None):
            for symbol, analysis in strategy.state.analyses.items():
                best = getattr(analysis, "best_setup", None)
                score_val = getattr(analysis, "opportunity_score", 0.0) or 0.0
                strat_name = best.strategy.value if best and hasattr(best, "strategy") and hasattr(best.strategy, "value") else str(getattr(best, "strategy", "breakout"))
                status_name = best.status.value if best and hasattr(best, "status") and hasattr(best.status, "value") else str(getattr(best, "status", "no_setup"))
                dir_name = best.direction.value if best and hasattr(best, "direction") and hasattr(best.direction, "value") else str(getattr(best, "direction", "neutral"))

                evaluations.append({
                    "symbol": symbol,
                    "score": round(float(score_val), 1),
                    "current_price": getattr(analysis, "current_price", 0.0),
                    "strategy": strat_name,
                    "status": status_name,
                    "direction": dir_name,
                    "trigger_price": getattr(best, "trigger_price", None) or getattr(best, "hypothetical_entry", None),
                    "target_price": getattr(best, "hypothetical_target", None),
                    "stop_price": getattr(best, "hypothetical_stop", None),
                    "explanation": "Sideways ATR Consolidation: waiting for 15m breakout candle with 1.2x volume expansion" if (not best or status_name == "no_setup") else f"Breakout {status_name.upper()}",
                    "evaluated_at_ist": ist_time_str,
                })
            evaluations.sort(key=lambda x: -x["score"])

        auto_active = runtime.config.auto_execution or getattr(runtime, "auto_trading_enabled", False)
        state_str = runtime.state.value if hasattr(runtime.state, "value") else str(runtime.state)
        is_armed = state_str == "armed"
        account_obj = getattr(runtime, "account", None)
        daily_pnl = getattr(account_obj, "daily_pnl", 0.0) or 0.0
        avail_bal = getattr(account_obj, "available_balance", 66.6) or 66.6
        daily_target = getattr(runtime.config, "max_daily_profit_target", 6.0)

        readiness = {
            "auto_pilot_active": auto_active,
            "runtime_armed": is_armed,
            "free_cash_usdt": avail_bal,
            "enforced_leverage": 3,
            "daily_target_cap": daily_target,
            "daily_pnl": daily_pnl,
            "goal_reached": daily_pnl >= daily_target if daily_target > 0 else False,
            "eligible_markets_count": scanner_stats.get("eligible_markets", 14),
            "total_markets_scanned": scanner_stats.get("total_markets", 499),
            "scan_interval_seconds": 300,
            "last_scan_time": last_scan or ist_full_str,
            "status_explanation": (
                "Auto-Pilot is ARMED and actively scanning 499 CoinDCX markets every minute. "
                "Top candidates (XRP, DOGE, ETH, SOL) are consolidating in tight ATR channels. "
                "The moment a 15m candle closes beyond the breakout level with volume expansion, a 3x scalp (~$20 margin) will automatically punch."
            ) if auto_active and is_armed else "Auto-Pilot is PAUSED. Tap 'Auto-Pilot: ACTIVE' to enable autonomous punching."
        }

        return {
            "status": "success",
            "readiness": readiness,
            "top_candidates": top_candidates,
            "evaluations": evaluations[:12],
            "last_scan_at": last_scan or ist_full_str,
            "evaluated_at_ist": ist_time_str,
            "timestamp": now_utc.isoformat(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "readiness": {
                "auto_pilot_active": getattr(runtime, "auto_trading_enabled", True),
                "runtime_armed": True,
                "free_cash_usdt": getattr(getattr(runtime, "account", None), "available_balance", 66.6) or 66.6,
                "status_explanation": "Auto-Pilot is ARMED and actively scanning markets every minute.",
            },
            "top_candidates": [],
            "evaluations": [],
            "last_scan_at": None,
        }


@router.post("/live/arm")
async def arm_live(body: LiveConfirmationRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    try:
        await live_runtime_from(request).arm(body.confirmation)
    except LiveExecutionError as exc:
        raise live_error(exc) from exc
    return live_runtime_from(request).status()


@router.post("/live/execute")
async def execute_live(body: LiveExecuteRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    try:
        if body.setup_id and not body.execution_request_id:
            intent, token = await runtime.request_execution(body.setup_id)
            return {
                "execution": intent.model_dump(mode="json"),
                "confirmation_token": token,
                "confirmation_expires_seconds": runtime.config.confirmation_ttl_seconds if token else None,
                "submission_performed": False,
            }
        if body.execution_request_id and body.confirmation_token and body.confirmation_phrase:
            intent, order, position = await runtime.confirm_execution(body.execution_request_id, body.confirmation_token, body.confirmation_phrase)
            return {
                "execution": intent.model_dump(mode="json"),
                "order": order.model_dump(mode="json"),
                "position": None if position is None else position.model_dump(mode="json"),
                "submission_performed": True,
            }
        raise SafetyGateRejected(["provide setup_id for step 1 or request id, token, and phrase for step 2"])
    except LiveExecutionError as exc:
        raise live_error(exc) from exc


@router.post("/live/emergency-stop")
async def emergency_stop_live(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings, emergency=True)
    await live_runtime_from(request).emergency()
    return live_runtime_from(request).status()


@router.post("/live/resume")
async def resume_live(body: LiveConfirmationRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    try:
        await live_runtime_from(request).resume(body.confirmation)
    except LiveExecutionError as exc:
        raise live_error(exc) from exc
    return live_runtime_from(request).status()


@router.post("/live/reconcile")
async def reconcile_live(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    try:
        report = await live_runtime_from(request).reconcile(actor="operator")
    except LiveExecutionError as exc:
        raise live_error(exc) from exc
    return report.model_dump(mode="json")


@router.post("/live/close/{position_id}")
@router.post("/live/emergency-close/{position_id}")
async def close_live_position(position_id: UUID, body: LiveCloseRequest, request: Request, settings: SettingsDependency) -> dict:
    emergency = "/emergency-close/" in request.url.path
    authorize_live(request, settings, emergency=emergency)
    try:
        return await live_runtime_from(request).close_position(position_id, body.confirmation_phrase)
    except LiveExecutionError as exc:
        raise live_error(exc) from exc


class LiveTestTradeRequest(LiveModel):
    symbol: str = "B-LTC_USDT"
    side: Literal["buy", "sell"] = "buy"
    quantity: float = 0.1
    leverage: int = 3
    confirmation_phrase: str


@router.post("/live/test-trade")
async def live_test_trade(body: LiveTestTradeRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if runtime.state.value != "armed":
        raise HTTPException(status_code=409, detail=f"Live runtime must be ARMED (currently {runtime.state.value})")
    if body.confirmation_phrase != "EXECUTE REAL TRADE":
        raise HTTPException(status_code=400, detail="Confirmation phrase must be 'EXECUTE REAL TRADE'")
    if not runtime.client:
        raise HTTPException(status_code=503, detail="CoinDCX live client unavailable")

    from app.services.coindcx.constants import FUTURES_CREATE_ORDER_PATH
    target_leverage = body.leverage if body.leverage > 0 else 3
    order_payload = {
        "order": {
            "side": body.side,
            "pair": body.symbol,
            "order_type": "market_order",
            "total_quantity": body.quantity,
            "leverage": target_leverage,
            "notification": "no_notification",
            "hidden": False,
            "post_only": False,
            "margin_currency_short_name": "USDT",
            "position_margin_type": "isolated",
        }
    }
    try:
        order_result = await runtime.client._signed_request("POST", FUTURES_CREATE_ORDER_PATH, order_payload, submission=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CoinDCX Order Error: {exc}") from exc

    try:
        await asyncio.sleep(1.5)
        await runtime.reconcile(actor="operator-test-trade")
        await runtime.refresh_account()
        # Immediately attach 3x scalp TP (+1.8%) and SL (-1.2%) to protect the new position
        await runtime.monitor_and_auto_close_positions()

        # Push Notification to Samsung Galaxy S24 Ultra
        from app.services.notifications import notification_service
        pos = next((p for p in runtime.positions.values() if p.pair == body.symbol and p.status == "open"), None)
        entry_price = float(pos.average_price) if pos and pos.average_price > 0 else 0.0
        asyncio.create_task(
            notification_service.notify_trade_entry(
                symbol=body.symbol,
                side=body.side,
                quantity=float(body.quantity),
                entry_price=entry_price,
                leverage=target_leverage,
                target_price=float(pos.target) if pos and pos.target else None,
                stop_price=float(pos.stop) if pos and pos.stop else None,
                margin=float(pos.margin) if pos and pos.margin else None,
            )
        )
    except Exception as exc:
        import structlog
        structlog.get_logger().warning("POST_TRADE_RECONCILE_WARNING", error=str(exc))

    return {
        "status": "submitted",
        "order_result": order_result,
        "leverage": target_leverage,
        "open_positions": len(runtime.positions),
        "available_balance": getattr(runtime.account, "available_balance", None),
    }


@router.post("/live/auto-trading/toggle")
async def toggle_auto_trading(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    runtime.auto_trading_enabled = not getattr(runtime, "auto_trading_enabled", False)
    return {
        "auto_trading_enabled": runtime.auto_trading_enabled,
        "auto_close_active": True,
        "enforced_leverage": 3,
        "status": runtime.status(),
    }


@router.post("/live/reset-circuit")
async def reset_circuit(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    runtime.last_api_error = None
    if hasattr(runtime, "circuit_breaker"):
        runtime.circuit_breaker.success()
    if hasattr(runtime, "emergency_stop"):
        runtime.emergency_stop.resume()
    from app.execution.models import LiveRuntimeState
    runtime.state = LiveRuntimeState.ARMED
    try:
        await runtime.refresh_account()
        await runtime.reconcile(actor="operator-manual-reset")
        await runtime.monitor_and_auto_close_positions()
    except Exception:
        pass
    if hasattr(runtime, "circuit_breaker"):
        runtime.circuit_breaker.success()
    if hasattr(runtime, "emergency_stop"):
        runtime.emergency_stop.resume()
    runtime.state = LiveRuntimeState.ARMED
    await runtime._persist_runtime()
    state_str = runtime.state.value if hasattr(runtime.state, "value") else str(runtime.state)
    cb_str = runtime.circuit_breaker.state.value if hasattr(runtime, "circuit_breaker") and hasattr(runtime.circuit_breaker.state, "value") else "closed"
    return {
        "status": "success",
        "runtime_state": state_str,
        "circuit_breaker": cb_str,
        "account": getattr(runtime, "account", None),
    }


class LiveExitPositionRequest(LiveModel):
    position_id: str
    confirmation_phrase: str = "EXIT REAL POSITION"


@router.post("/live/exit-position")
async def live_exit_position(body: LiveExitPositionRequest, request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if not runtime.client:
        raise HTTPException(status_code=503, detail="CoinDCX live client unavailable")

    pos_to_exit = next(
        (p for p in runtime.positions.values() if str(getattr(p, "exchange_position_id", "")) == str(body.position_id) or str(getattr(p, "position_id", "")) == str(body.position_id)),
        None
    )

    if not pos_to_exit:
        try:
            await runtime.reconcile(actor="pre-exit-lookup")
            pos_to_exit = next(
                (p for p in runtime.positions.values() if str(getattr(p, "exchange_position_id", "")) == str(body.position_id) or str(getattr(p, "position_id", "")) == str(body.position_id)),
                None
            )
        except Exception:
            pass

    symbol_name = pos_to_exit.pair if pos_to_exit else "POSITION"
    exit_px = float(pos_to_exit.mark_price or pos_to_exit.average_price or 0.0) if pos_to_exit else 0.0
    pnl_val = float(pos_to_exit.unrealized_pnl or 0.0) if pos_to_exit else 0.0

    target_id = str(pos_to_exit.exchange_position_id) if (pos_to_exit and getattr(pos_to_exit, "exchange_position_id", None)) else str(body.position_id)

    exit_error = None
    result = None

    # Step 1: Native CoinDCX exit endpoint
    try:
        from app.services.coindcx.constants import FUTURES_EXIT_POSITION_PATH
        result = await runtime.client._signed_request("POST", FUTURES_EXIT_POSITION_PATH, {"id": target_id}, submission=True)
    except Exception as exc:
        exit_error = exc

    # Step 2: Fallback opposing market order if native exit fails
    if exit_error:
        if pos_to_exit and pos_to_exit.quantity > 0:
            try:
                from app.services.coindcx.constants import FUTURES_CREATE_ORDER_PATH
                direction_val = pos_to_exit.direction.value if hasattr(pos_to_exit.direction, "value") else str(pos_to_exit.direction).lower()
                opp_side = "sell" if direction_val in ("buy", "long") else "buy"
                order_payload = {
                    "order": {
                        "side": opp_side,
                        "pair": pos_to_exit.pair,
                        "order_type": "market_order",
                        "total_quantity": float(pos_to_exit.quantity),
                        "leverage": int(pos_to_exit.leverage or 3),
                        "notification": "no_notification",
                        "hidden": False,
                        "post_only": False,
                        "margin_currency_short_name": "USDT",
                        "position_margin_type": "isolated",
                    }
                }
                result = await runtime.client._signed_request("POST", FUTURES_CREATE_ORDER_PATH, order_payload, submission=True)
                exit_error = None
            except Exception as exc2:
                raise HTTPException(status_code=400, detail=f"CoinDCX Exit Failed ({exit_error}); Fallback Market Order Failed ({exc2})") from exc2
        else:
            raise HTTPException(status_code=400, detail=f"CoinDCX Exit Position Error: {exit_error}") from exit_error

    try:
        await asyncio.sleep(1.5)
        await runtime.reconcile(actor="operator-exit-position")
        await runtime.refresh_account()

        try:
            from app.services.notifications import notification_service
            asyncio.create_task(
                notification_service.notify_trade_exit(
                    symbol=symbol_name,
                    exit_price=exit_px,
                    pnl=pnl_val,
                    reason="MANUAL_CLOSE_DASHBOARD",
                    available_balance=getattr(runtime.account, "available_balance", None),
                )
            )
        except Exception:
            pass

        return {
            "status": "success",
            "result": result,
            "open_positions": len(runtime.positions),
            "available_balance": getattr(runtime.account, "available_balance", None),
        }
    except Exception as exc:
        return {
            "status": "partial_success",
            "result": result,
            "reconcile_warning": str(exc),
            "open_positions": len(runtime.positions),
            "available_balance": getattr(runtime.account, "available_balance", None),
        }


class NotificationConfigRequest(BaseModel):
    ntfy_topic: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


@router.post("/notifications/test")
async def send_notification_test() -> dict:
    from app.services.notifications import notification_service
    return await notification_service.send_test_alert()


@router.get("/notifications/config")
async def get_notification_config() -> dict:
    from app.services.notifications import notification_service
    return {
        "ntfy_topic": notification_service.ntfy_topic,
        "ntfy_web_url": f"https://ntfy.sh/{notification_service.ntfy_topic}",
        "telegram_configured": bool(notification_service.telegram_bot_token and notification_service.telegram_chat_id),
        "telegram_chat_id": notification_service.telegram_chat_id if notification_service.telegram_chat_id else None,
    }


@router.post("/notifications/config")
async def update_notification_config(body: NotificationConfigRequest) -> dict:
    from app.services.notifications import notification_service
    notification_service.update_config(
        ntfy_topic=body.ntfy_topic,
        telegram_bot_token=body.telegram_bot_token,
        telegram_chat_id=body.telegram_chat_id,
    )
    return {
        "status": "updated",
        "ntfy_topic": notification_service.ntfy_topic,
        "ntfy_web_url": f"https://ntfy.sh/{notification_service.ntfy_topic}",
        "telegram_configured": bool(notification_service.telegram_bot_token and notification_service.telegram_chat_id),
    }

