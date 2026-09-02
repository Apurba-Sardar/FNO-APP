import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.backtesting.state import BacktestRuntime, BacktestStateStore
from app.clients.coindcx import CoinDCXError
from app.config import get_settings
from app.db.session import SessionLocal, initialize_database
from app.execution.repository import LiveExecutionRepository
from app.execution.runtime import LiveExecutionRuntime
from app.indicators import IndicatorEngine
from app.market_data.runtime import MarketDataRuntime
from app.paper_trading.engine import PaperTradingRuntime
from app.paper_trading.state import PaperStateRepository
from app.risk.engine import RiskEngine
from app.risk.state import RiskRuntime, RiskStateStore
from app.scanner.scanner import AllMarketScanner
from app.scanner.scheduler import ScannerRuntime
from app.scanner.state import ScannerStateStore
from app.scoring.engine import OpportunityScoringEngine
from app.scoring.state import OpportunityRuntime, OpportunityState
from app.services.coindcx.authenticated_client import AuthenticatedCoinDCXClient
from app.strategy.context import StrategyContextBuilder
from app.strategy.engine import StrategyEngine
from app.strategy.state import StrategyRuntime, StrategyState


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


configure_logging()
settings = get_settings()


def create_authenticated_live_client(configuration):
    if not (
        configuration.trading_mode == "live"
        and configuration.coindcx_api_key
        and configuration.coindcx_api_secret
    ):
        return None
    return AuthenticatedCoinDCXClient(
        api_base_url=configuration.coindcx_api_base_url,
        api_key=configuration.coindcx_api_key,
        api_secret=configuration.coindcx_api_secret,
        timeout=configuration.live.order_timeout_seconds,
        requests_per_second=min(configuration.coindcx_requests_per_second, 10),
        max_retries=configuration.live.max_order_retries,
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    runtime = MarketDataRuntime(settings)
    application.state.market_data_runtime = runtime
    scanner_state = ScannerStateStore(
        runtime.redis,
        settings.market_scanner.interval_seconds,
        settings.market_scanner.state_ttl_seconds,
    )
    scanner_runtime = ScannerRuntime(
        AllMarketScanner(settings, settings.market_scanner, scanner_state, runtime.store),
        scanner_state,
        settings.market_scanner,
    )
    opportunity_state = OpportunityState(runtime.redis, settings.scoring)
    opportunity_runtime = OpportunityRuntime(
        scanner_state,
        opportunity_state,
        OpportunityScoringEngine(settings.scoring),
    )
    strategy_state = StrategyState(runtime.redis, settings.strategy)
    strategy_runtime = StrategyRuntime(
        scanner_state,
        opportunity_state,
        strategy_state,
        StrategyEngine(
            StrategyContextBuilder(IndicatorEngine(settings.analysis), settings.strategy),
            settings.strategy,
        ),
        settings.strategy,
    )
    risk_state = RiskStateStore(runtime.redis, settings.risk)
    risk_runtime = RiskRuntime(
        scanner_state,
        strategy_state,
        risk_state,
        RiskEngine(settings.risk),
        settings.risk,
    )
    backtest_state = BacktestStateStore(runtime.redis)
    backtest_runtime = BacktestRuntime(SessionLocal, backtest_state)
    paper_runtime = PaperTradingRuntime(
        PaperStateRepository(SessionLocal, settings.paper.initial_equity),
        runtime,
        scanner_state,
        opportunity_state,
        strategy_state,
        risk_state,
        settings.paper,
        settings.risk,
    )
    live_client = create_authenticated_live_client(settings)
    live_runtime = LiveExecutionRuntime(
        settings.live,
        LiveExecutionRepository(SessionLocal),
        client=live_client,
        strategy_runtime=strategy_runtime,
        risk_runtime=risk_runtime,
        market_runtime=runtime,
    )
    scanner_runtime.on_completed = opportunity_runtime.recalculate
    opportunity_runtime.on_completed = strategy_runtime.evaluate_all
    async def risk_then_paper(source_stats):
        now = getattr(source_stats, "evaluated_at", None) or datetime.now(UTC)
        risk_stats = await risk_runtime.evaluate_all(
            source_stats,
            evaluation_timestamp=now,
            account=paper_runtime.risk_account(now),
            persist_account=True,
        )
        await paper_runtime.process_risk_results(risk_stats)
        return risk_stats

    strategy_runtime.on_completed = risk_then_paper
    application.state.scanner_runtime = scanner_runtime
    application.state.opportunity_runtime = opportunity_runtime
    application.state.strategy_runtime = strategy_runtime
    application.state.risk_runtime = risk_runtime
    application.state.backtest_runtime = backtest_runtime
    application.state.paper_runtime = paper_runtime
    application.state.live_runtime = live_runtime
    try:
        await initialize_database()
    except Exception as exc:  # noqa: BLE001 - health reports an unavailable database
        structlog.get_logger().error("DATABASE_INITIALIZATION_ERROR", error=str(exc))
    await scanner_state.load()
    await opportunity_state.load()
    await strategy_state.load()
    await risk_state.load()
    await backtest_state.load()
    await paper_runtime.load()
    risk_state.update_account(paper_runtime.risk_account(datetime.now(UTC)), datetime.now(UTC))
    await risk_state.persist()
    await runtime.start()
    await live_runtime.start()
    await scanner_runtime.start_runtime()
    if settings.paper.auto_start:
        await paper_runtime.start()
    try:
        yield
    finally:
        await live_runtime.shutdown()
        await paper_runtime.shutdown()
        await scanner_runtime.shutdown()
        await runtime.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CoinDCX analysis, paper simulation, and fail-closed staged live execution",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(CoinDCXError)
async def coindcx_error_handler(_: Request, exc: CoinDCXError) -> JSONResponse:
    structlog.get_logger().warning("coindcx_public_request_failed", error=str(exc))
    return JSONResponse(status_code=502, content={"detail": "CoinDCX market data is unavailable"})


app.include_router(router)
