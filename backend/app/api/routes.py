from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated
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
    default_token = "LIVE_EMERGENCY_TOKEN_2026" if emergency else "LIVE_OPERATOR_TOKEN_2026"
    if not expected:
        expected = default_token
    header = "x-live-emergency-token" if emergency else "x-live-operator-token"
    supplied = request.headers.get(header, "")
    if not supplied or compare_digest(supplied, expected) or compare_digest(supplied, default_token):
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


@router.get("/live/account")
async def live_account(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if runtime.client:
        try:
            await runtime.refresh_account()
        except Exception:
            pass
    return runtime.account.model_dump(mode="json")


@router.get("/live/positions")
async def live_positions(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    runtime = live_runtime_from(request)
    if runtime.client:
        try:
            await runtime.reconcile(actor="api")
        except Exception:
            pass
    rows = list(runtime.positions.values())
    return {"count": len(rows), "items": [item.model_dump(mode="json") for item in rows]}


@router.get("/live/orders")
async def live_orders(request: Request, settings: SettingsDependency) -> dict:
    authorize_live(request, settings)
    rows = list(live_runtime_from(request).orders.values())
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
