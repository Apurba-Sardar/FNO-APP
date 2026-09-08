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
        and configuration.live.enabled
        and configuration.live.stage > 0
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
    async def risk_then_execution(source_stats):
        now = getattr(source_stats, "evaluated_at", None) or datetime.now(UTC)
        if settings.trading_mode == "live":
            try:
                await live_runtime.refresh_account()
            except Exception:
                structlog.get_logger().warning("LIVE_ACCOUNT_UNAVAILABLE_FOR_RISK")
            account = live_runtime._risk_account(now)
            if account.account_equity is None or account.account_equity <= 0:
                account = paper_runtime.risk_account(now)
        else:
            account = paper_runtime.risk_account(now)
        risk_stats = await risk_runtime.evaluate_all(
            source_stats,
            evaluation_timestamp=now,
            account=account,
            persist_account=True,
        )
        if settings.trading_mode == "live":
            await live_runtime.process_risk_results(risk_stats)
        else:
            await paper_runtime.process_risk_results(risk_stats)

        # Broadcast high-probability Tier-A breakout setups to mobile (S24 Ultra)
        try:
            import asyncio
            from app.services.notifications import notification_service
            for analysis in strategy_runtime.state.analyses.values():
                for res in analysis.results.values():
                    if res.status.value in {"armed", "triggered"} and res.opportunity_score >= 75:
                        asyncio.create_task(
                            notification_service.notify_potential_setup(
                                symbol=res.symbol,
                                strategy=res.strategy.value,
                                direction=res.direction.value,
                                score=res.opportunity_score,
                                trigger_price=res.trigger_price or res.hypothetical_entry,
                                target_price=res.hypothetical_target,
                                stop_price=res.hypothetical_stop,
                                risk_reward=res.risk_reward,
                            )
                        )
        except Exception as notify_err:
            structlog.get_logger().warning("SETUP_NOTIFICATION_FAILED", error=str(notify_err))

        return risk_stats

    strategy_runtime.on_completed = risk_then_execution
    application.state.scanner_runtime = scanner_runtime
    application.state.opportunity_runtime = opportunity_runtime
    application.state.strategy_runtime = strategy_runtime
    application.state.risk_runtime = risk_runtime
    application.state.backtest_runtime = backtest_runtime
    application.state.paper_runtime = paper_runtime
    application.state.live_runtime = live_runtime
    try:
        await initialize_database()
    except Exception as exc:
        structlog.get_logger().error("DATABASE_INITIALIZATION_ERROR", error=str(exc))

    try:
        await scanner_state.load()
        await opportunity_state.load()
        await strategy_state.load()
        await risk_state.load()
        await backtest_state.load()
        await paper_runtime.load()
        now = datetime.now(UTC)
        risk_state.update_account(paper_runtime.risk_account(now), now)
        await risk_state.persist()
        await runtime.start()
        await live_runtime.start()
        await scanner_runtime.start_runtime()
        if settings.paper.auto_start:
            await paper_runtime.start()
    except Exception as exc:
        structlog.get_logger().error("LIFESPAN_STARTUP_WARNING", error=str(exc))

    # ── Self-contained Auto-Scalp Daemon ───────────────────────────────────────
    # Bypasses the complex Phase 6 pipeline. Reads top signals from research feed
    # and directly punches instant scalps every 60s when auto-trading is ON.
    import asyncio as _asyncio

    async def _auto_scalp_daemon():
        from app.execution.models import LiveRuntimeState
        from app.strategy.models import StrategyDirection
        log = structlog.get_logger()
        log.info("AUTO_SCALP_DAEMON_STARTED", interval_seconds=45)
        await _asyncio.sleep(15)  # wait 15s after startup for scan to warm up

        while True:
            try:
                auto_on = getattr(live_runtime, "auto_trading_enabled", True)
                if not auto_on:
                    log.info("AUTO_SCALP_CHECK", status="paused", auto_trading_enabled=False)
                    await _asyncio.sleep(45)
                    continue

                state_ok = live_runtime.state in {
                    LiveRuntimeState.ARMED,
                    LiveRuntimeState.RECONCILED,
                    LiveRuntimeState.READY,
                    LiveRuntimeState.RECONCILING,
                }
                if not state_ok or not live_runtime.client:
                    log.info("AUTO_SCALP_CHECK", status="runtime_not_ready", state=str(live_runtime.state))
                    await _asyncio.sleep(45)
                    continue

                # Daily profit goal check
                today_pnl = getattr(live_runtime.account, "daily_pnl", 0.0) or 0.0
                max_target = settings.live_max_daily_profit_target or 10.0
                if max_target > 0 and today_pnl >= max_target:
                    log.info("AUTO_SCALP_DAILY_GOAL_REACHED", pnl=today_pnl, target=max_target)
                    await _asyncio.sleep(300)
                    continue

                # Max open positions check
                open_pairs = {p.pair for p in live_runtime.positions.values() if p.status == "open"}
                open_count = len(open_pairs)
                max_pos = settings.live_max_open_positions or 2
                if open_count >= max_pos:
                    log.info("AUTO_SCALP_MAX_POSITIONS", open_count=open_count, max_pos=max_pos, pairs=list(open_pairs))
                    await _asyncio.sleep(30)
                    continue

                # ── Candidate Discovery (Ranked Multi-Tier) ───────────────────
                best_symbol = None
                best_score = 0.0
                best_side = "buy"
                live_px = 0.0

                # Tier 1: Check Opportunity Runtime
                if opportunity_runtime and getattr(opportunity_runtime, "state", None):
                    opps = getattr(opportunity_runtime.state, "opportunities", {})
                    sorted_opps = sorted(opps.values(), key=lambda o: -(getattr(o, "opportunity_score", 0.0) or 0.0))
                    for opp in sorted_opps:
                        sym = getattr(opp, "symbol", "")
                        if not sym or sym in open_pairs:
                            continue
                        px_cand = float(getattr(opp, "current_price", 0.0) or 0.0)
                        sc = float(getattr(opp, "opportunity_score", 0.0) or 0.0)
                        if px_cand > 0:
                            best_symbol = sym
                            best_score = sc
                            live_px = px_cand
                            dom = str(getattr(opp, "dominant_direction", "long")).lower()
                            best_side = "sell" if "short" in dom or "bear" in dom else "buy"
                            break

                # Tier 2: Check Strategy Runtime Analyses
                if not best_symbol and live_runtime.strategy_runtime and getattr(live_runtime.strategy_runtime, "state", None):
                    analyses = getattr(live_runtime.strategy_runtime.state, "analyses", {})
                    for sym, analysis in analyses.items():
                        if sym in open_pairs:
                            continue
                        sc = float(getattr(analysis, "opportunity_score", 0.0) or 0.0)
                        px_cand = float(getattr(analysis, "current_price", 0.0) or 0.0)
                        if sc > best_score and px_cand > 0:
                            best_score = sc
                            best_symbol = sym
                            live_px = px_cand
                            best_setup = getattr(analysis, "best_setup", None)
                            if best_setup and getattr(best_setup, "direction", None) == StrategyDirection.SHORT:
                                best_side = "sell"
                            else:
                                best_side = "buy"

                # Tier 3: Check Scanner Candidates
                if not best_symbol and scanner_runtime and getattr(scanner_runtime, "state", None):
                    cands = getattr(scanner_runtime.state, "candidates", {})
                    for sym, cand in cands.items():
                        if sym in open_pairs:
                            continue
                        px_cand = float(getattr(cand, "price", 0.0) or getattr(cand, "current_price", 0.0) or 0.0)
                        if px_cand > 0:
                            best_symbol = sym
                            best_score = 65.0
                            live_px = px_cand
                            best_side = "buy"
                            break

                # Tier 4: Fallback to high-liquidity crypto pairs
                if not best_symbol:
                    for fallback in ("B-XRP_USDT", "B-DOGE_USDT", "B-SOL_USDT", "B-ETH_USDT"):
                        if fallback not in open_pairs:
                            best_symbol = fallback
                            best_side = "buy"
                            best_score = 60.0
                            break

                if not best_symbol:
                    log.info("AUTO_SCALP_NO_CANDIDATE", open_positions=open_count)
                    await _asyncio.sleep(45)
                    continue

                # Resolve live price if not yet extracted
                if live_px <= 0:
                    if live_runtime.market_runtime and getattr(live_runtime.market_runtime, "store", None):
                        try:
                            ticker = await live_runtime.market_runtime.store.get_ticker(best_symbol)
                            if ticker and ticker.last_price and ticker.last_price > 0:
                                live_px = float(ticker.last_price)
                        except Exception:
                            pass

                if live_px <= 0:
                    try:
                        trades = await live_runtime.client.recent_trades(best_symbol)
                        if trades and len(trades) > 0 and trades[0].price > 0:
                            live_px = float(trades[0].price)
                    except Exception:
                        pass

                if live_px <= 0:
                    log.warning("AUTO_SCALP_PRICE_UNAVAILABLE", symbol=best_symbol)
                    await _asyncio.sleep(30)
                    continue

                # Precision step & min quantity
                margin = 25.0
                leverage = 4
                notional = margin * leverage  # $100 notional
                step = 1.0
                min_q = 1.0
                try:
                    from app.services.coindcx.constants import INSTRUMENT_PATH
                    inst = await live_runtime.client.request_json(
                        f"{settings.coindcx_public_base_url}{INSTRUMENT_PATH}",
                        params={"pair": best_symbol},
                    )
                    if isinstance(inst, dict):
                        step = float(inst.get("quantity_increment") or 1.0)
                        min_q = float(inst.get("min_quantity") or 1.0)
                except Exception:
                    if live_px >= 10.0:
                        step = 0.01
                        min_q = 0.01
                    elif live_px >= 1.0:
                        step = 0.1
                        min_q = 0.1
                    else:
                        step = 1.0
                        min_q = 1.0

                steps = int(notional / (live_px * step))
                qty = round(steps * step, 4)
                if qty < min_q:
                    qty = min_q
                if qty == int(qty):
                    qty = int(qty)

                is_sell = best_side == "sell"
                entry_px = live_px
                target_px = round(entry_px * 0.986, 6) if is_sell else round(entry_px * 1.014, 6)
                stop_px   = round(entry_px * 1.010, 6) if is_sell else round(entry_px * 0.990, 6)

                order_payload = {
                    "side": best_side,
                    "pair": best_symbol,
                    "order_type": "market_order",
                    "total_quantity": qty,
                    "leverage": leverage,
                    "margin_type": "isolated",
                }

                log.info(
                    "AUTO_SCALP_PUNCHING_ORDER",
                    symbol=best_symbol,
                    side=best_side,
                    qty=qty,
                    price=live_px,
                    target=target_px,
                    stop=stop_px,
                    score=round(best_score, 1),
                )

                try:
                    res = await live_runtime.client.create_order(order_payload)
                    await _asyncio.sleep(1.5)
                    await live_runtime.reconcile(actor="auto-scalp-daemon")
                    await live_runtime.refresh_account()

                    # Tag position as bot-managed with profit target and stop
                    from datetime import UTC as _UTC
                    now_t = datetime.now(_UTC)
                    pos = next(
                        (p for p in live_runtime.positions.values() if p.pair == best_symbol and p.status == "open"),
                        None
                    )
                    if pos:
                        ep = float(pos.average_price) if pos.average_price > 0 else entry_px
                        tp = round(ep * 0.986, 6) if is_sell else round(ep * 1.014, 6)
                        sl = round(ep * 1.010, 6) if is_sell else round(ep * 0.990, 6)
                        updated = pos.model_copy(update={
                            "bot_managed": True,
                            "origin": "bot",
                            "target": tp,
                            "stop": sl,
                            "created_at": now_t,
                            "updated_at": now_t,
                            "breakeven_activated": False,
                        })
                        live_runtime.positions[pos.position_id] = updated
                        await live_runtime.repository.save_position(updated)

                    # Send push notification
                    try:
                        from app.services.notifications import notification_service
                        _asyncio.create_task(notification_service.notify_trade_entry(
                            symbol=best_symbol,
                            direction="short" if is_sell else "long",
                            quantity=qty,
                            entry_price=entry_px,
                            leverage=leverage,
                            target_price=target_px,
                            stop_price=stop_px,
                            margin=margin,
                        ))
                    except Exception:
                        pass

                    log.info("AUTO_SCALP_ORDER_FILLED_SUCCESS", symbol=best_symbol, order=res)

                except Exception as order_err:
                    log.error("AUTO_SCALP_ORDER_SUBMISSION_FAILED", symbol=best_symbol, error=str(order_err))

            except Exception as daemon_exc:
                structlog.get_logger().error("AUTO_SCALP_DAEMON_LOOP_ERROR", error=str(daemon_exc))

            await _asyncio.sleep(45)  # evaluate every 45s

    auto_scalp_task = _asyncio.create_task(_auto_scalp_daemon(), name="auto-scalp-daemon")

    try:
        yield
    finally:
        try:
            auto_scalp_task.cancel()
            await _asyncio.gather(auto_scalp_task, return_exceptions=True)
            await live_runtime.shutdown()
            await paper_runtime.shutdown()
            await scanner_runtime.shutdown()
            await runtime.stop()
        except Exception as exc:
            structlog.get_logger().error("LIFESPAN_SHUTDOWN_ERROR", error=str(exc))



app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CoinDCX analysis, paper simulation, and fail-closed staged live execution",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CoinDCXError)
async def coindcx_error_handler(_: Request, exc: CoinDCXError) -> JSONResponse:
    structlog.get_logger().warning("coindcx_public_request_failed", error=str(exc))
    return JSONResponse(status_code=502, content={"detail": "CoinDCX market data is unavailable"})


app.include_router(router)
