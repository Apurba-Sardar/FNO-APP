import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.strategy.models import StrategyStatus

from .analytics import compare_metrics, performance
from .config import PaperTradingConfig
from .drift import PerformanceDriftMonitor
from .exceptions import PaperExecutionRejected
from .execution import PaperTradeExecutor
from .models import (
    EngineStatus,
    MarketQuote,
    PaperEvent,
    PaperExitReason,
    PaperPositionStatus,
    PaperSession,
    PaperSetupState,
    PaperSetupStatus,
)
from .portfolio import account_snapshot, refresh_account
from .reconciliation import reconcile


class PaperTradingRuntime:
    def __init__(
        self,
        repository,
        market_runtime,
        scanner_state,
        opportunity_state,
        strategy_state,
        risk_state,
        config,
        risk_config,
    ):
        self.repository = repository
        self.market_runtime = market_runtime
        self.scanner_state = scanner_state
        self.opportunity_state = opportunity_state
        self.strategy_state = strategy_state
        self.risk_state = risk_state
        self.config: PaperTradingConfig = config
        self.risk_config = risk_config
        self.executor = PaperTradeExecutor(config, risk_config.taker_fee_percent)
        self.state = repository.new_state()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.log = structlog.get_logger()

    @property
    def current_session(self):
        return next((item for item in reversed(self.state.sessions) if item.end_time is None), None)

    async def load(self) -> None:
        self.state = await self.repository.load()
        warnings = reconcile(self.state)
        refresh_account(self.state)
        self.state.state_recovery_status = "restored" if not warnings else "reconciled_with_warnings"
        await self.repository.save(self.state)

    async def start(self) -> PaperSession:
        async with self._lock:
            if self.current_session is None:
                session = PaperSession(
                    start_time=datetime.now(UTC), initial_equity=self.state.account.equity,
                    configuration_snapshot=self.config.model_dump(mode="json"),
                    strategy_version=self.config.strategy_version, risk_version=self.config.risk_version,
                )
                self.state.sessions.append(session)
            self.state.engine_status = EngineStatus.RUNNING
            self._event("PAPER_ENGINE_STARTED")
            await self.repository.save(self.state)
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._monitor_loop(), name="paper-position-monitor")
            return self.current_session

    async def stop(self) -> None:
        self.state.engine_status = EngineStatus.STOPPED
        session = self.current_session
        if session:
            session.end_time = datetime.now(UTC)
            session.final_equity = self.state.account.equity
            session.trade_count = len([t for t in self.state.trades if t.session_id == session.session_id])
            session.net_pnl = self.state.account.equity - session.initial_equity
            session.max_drawdown = self.state.account.drawdown
        self._event("PAPER_ENGINE_STOPPED")
        await self.repository.save(self.state)
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def shutdown(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self.repository.save(self.state)

    def risk_account(self, now: datetime):
        refresh_account(self.state, now)
        return account_snapshot(self.state, now)

    async def process_risk_results(self, _stats=None) -> None:
        if self.state.engine_status != EngineStatus.RUNNING:
            return
        now = datetime.now(UTC)
        self.state.last_scan = getattr(self.scanner_state.stats, "scan_completed_at", None)
        self.state.last_strategy_evaluation = getattr(self.strategy_state.stats, "evaluated_at", None)
        self.state.last_risk_evaluation = now
        for symbol, analysis in sorted(self.strategy_state.analyses.items()):
            risk_analysis = self.risk_state.analyses.get(symbol)
            if risk_analysis is None:
                continue
            for strategy, setup in analysis.results.items():
                if setup.status not in {StrategyStatus.TRIGGERED, StrategyStatus.INVALIDATED, StrategyStatus.EXPIRED}:
                    continue
                setup_id = f"{symbol}:{strategy.value}:{setup.evaluation_timestamp.isoformat()}"
                if setup.status != StrategyStatus.TRIGGERED:
                    await self._invalidation(setup_id, setup, now)
                    continue
                previous_setup = self.state.setups.get(setup_id)
                if previous_setup and previous_setup.status != PaperSetupStatus.ARMED:
                    continue
                if previous_setup is None:
                    self.state.counters.setups_detected += 1
                    self._event("PAPER_SETUP_RECEIVED", setup, setup_id=setup_id)
                decision = risk_analysis.decisions.get(strategy)
                if decision is None or not decision.allowed:
                    self.state.counters.risk_rejected += 1
                    self.state.setups[setup_id] = PaperSetupState(
                        setup_id=setup_id, symbol=symbol, strategy=strategy,
                        status=PaperSetupStatus.REJECTED_BY_RISK,
                        trigger_timestamp=setup.evaluation_timestamp, updated_at=now,
                        reason="; ".join(decision.rejection_reasons) if decision else "risk decision unavailable",
                    )
                    self._event("PAPER_RISK_REJECTED", setup, setup_id=setup_id)
                    continue
                if previous_setup is None:
                    self.state.counters.risk_approved += 1
                    self._event("PAPER_RISK_APPROVED", setup, setup_id=setup_id)
                await self.market_runtime.websocket.subscribe_trades(symbol)
                await self.market_runtime.websocket.subscribe_orderbook(symbol)
                try:
                    quote = await self.quote(symbol)
                    candidate = self.scanner_state.candidates.get(symbol)
                    self.executor.execute_entry(
                        self.state, setup, decision, quote, now, setup_id,
                        market_regime=str(analysis.timeframe_trends.get("1h", "unknown")),
                        factor_snapshot={
                            "conditions": setup.conditions_met,
                            "evaluation_time": setup.evaluation_timestamp,
                            "planned_entry": setup.hypothetical_entry,
                            "risk_amount": decision.risk_amount,
                            "risk_percent": decision.risk_percent,
                            "risk_decision": decision.model_dump(mode="json"),
                            "strategy_explanation": setup.explanations,
                            "market_context": {
                                "timeframe_trends": {
                                    str(key): str(value)
                                    for key, value in analysis.timeframe_trends.items()
                                },
                                "conditions": setup.conditions_met,
                            },
                            "data_quality": {
                                "status": getattr(candidate, "data_quality_status", "unknown"),
                                "warnings": getattr(candidate, "warnings", []),
                                "market_timestamp": getattr(
                                    getattr(candidate, "market", None),
                                    "data_timestamp",
                                    None,
                                ),
                            },
                            "order_lifecycle": [
                                "intent_created", "validating", "submitting", "filled"
                            ],
                        },
                    )
                    status, reason = PaperSetupStatus.ENTERED, None
                except PaperExecutionRejected as exc:
                    status, reason = PaperSetupStatus.ARMED, str(exc)
                self.state.setups[setup_id] = PaperSetupState(
                    setup_id=setup_id, symbol=symbol, strategy=strategy, status=status,
                    trigger_timestamp=setup.evaluation_timestamp, updated_at=now, reason=reason,
                )
        await self.repository.save(self.state)

    async def quote(self, symbol: str) -> MarketQuote:
        book = await self.market_runtime.store.get_orderbook(symbol)
        trade = await self.market_runtime.store.get_latest_trade(symbol)
        ticker = await self.market_runtime.store.get_ticker(symbol)
        timestamps = [item.timestamp for item in (book, trade, ticker) if item is not None]
        if not timestamps:
            raise PaperExecutionRejected("live public market quote unavailable")
        return MarketQuote(
            symbol=symbol,
            bid=book.bids[0][0] if book and book.bids else None,
            ask=book.asks[0][0] if book and book.asks else None,
            last=trade.price if trade else ticker.last_price if ticker else None,
            timestamp=max(timestamps),
        )

    async def monitor_once(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        async with self._lock:
            had_stale = False
            for position in [p for p in self.state.positions if p.status == PaperPositionStatus.OPEN]:
                try:
                    quote = await self.quote(position.symbol)
                    self.executor.validate_quote(quote, now)
                    reason = self.executor.trigger_reason(
                        position, quote, now, self.risk_config.max_trade_duration_minutes
                    )
                    if reason:
                        await self._exit(position, quote, reason, now)
                except PaperExecutionRejected as exc:
                    had_stale = True
                    self.state.block_reason = str(exc)
            refresh_account(self.state, now)
            self.state.last_market_update = self.market_runtime.websocket.last_message_at
            risk_blocked = (
                self.risk_state.risk_state.trading_lock.value == "blocked"
                and "account data unavailable" not in (self.risk_state.risk_state.block_reasons or [])
            )
            self.state.trading_blocked = had_stale or risk_blocked
            if not self.state.trading_blocked:
                self.state.block_reason = None
            if had_stale:
                self.state.engine_status = EngineStatus.DATA_STALE
                self._event("PAPER_ENGINE_DATA_STALE")
            elif self.state.engine_status == EngineStatus.DATA_STALE:
                self.state.engine_status = EngineStatus.RUNNING
                self.state.block_reason = None
                self._event("PAPER_ENGINE_RECOVERED")
            await self.repository.save(self.state)

    async def close_position(self, position_id, reason=PaperExitReason.MANUAL):
        position = next((p for p in self.state.positions if p.position_id == position_id), None)
        if position is None or position.status != PaperPositionStatus.OPEN:
            raise PaperExecutionRejected("open paper position not found")
        quote = await self.quote(position.symbol)
        return await self._exit(position, quote, reason, datetime.now(UTC))

    async def _exit(self, position, quote, reason, now):
        session = self.current_session
        if session is None:
            raise PaperExecutionRejected("no active paper session")
        trade = self.executor.execute_exit(
            self.state, position, quote, reason, now, session.session_id,
            self.config.strategy_version, self.config.risk_version,
        )
        event_type = {
            PaperExitReason.STOP_LOSS: "PAPER_SL_HIT",
            PaperExitReason.TAKE_PROFIT: "PAPER_TP_HIT",
            PaperExitReason.TIME_EXIT: "PAPER_TIME_EXIT",
        }.get(reason)
        if event_type:
            self._event(event_type, setup_id=position.setup_id, position=position)
        self.state.cooldowns[position.symbol] = now + timedelta(minutes=self.config.symbol_cooldown_minutes)
        await self.repository.save(self.state)
        return trade

    async def _invalidation(self, setup_id, setup, now):
        current = self.state.setups.get(setup_id)
        if current and current.status != PaperSetupStatus.ENTERED:
            current.status = PaperSetupStatus.INVALIDATED if setup.status == StrategyStatus.INVALIDATED else PaperSetupStatus.EXPIRED
            current.updated_at = now
        position = next((p for p in self.state.positions if p.setup_id == setup_id and p.status == PaperPositionStatus.OPEN), None)
        if position:
            try:
                await self._exit(position, await self.quote(position.symbol), PaperExitReason.INVALIDATION, now)
            except PaperExecutionRejected:
                pass

    async def _monitor_loop(self):
        while self.state.engine_status in {EngineStatus.RUNNING, EngineStatus.DATA_STALE}:
            await asyncio.sleep(self.config.monitor_interval_seconds)
            await self.monitor_once()

    async def reset(self, confirmation: str) -> None:
        if self.config.reset_requires_confirmation and confirmation != "RESET PAPER TRADING":
            raise PaperExecutionRejected("exact reset confirmation is required")
        if any(p.status == PaperPositionStatus.OPEN for p in self.state.positions):
            raise PaperExecutionRejected("close open paper positions before reset")
        await self.repository.reset(self.state)
        self.state = await self.repository.load()

    def analytics(self, backtest=None):
        metrics = performance(self.state)
        comparison = compare_metrics(metrics, backtest)
        drift = PerformanceDriftMonitor(self.config.minimum_health_sample).evaluate(metrics, comparison)
        return metrics, comparison, drift

    def _event(self, event_type, setup=None, *, setup_id=None, position=None):
        now = datetime.now(UTC)
        event = PaperEvent(
            event_type=event_type, timestamp=now,
            symbol=getattr(setup, "symbol", None) or getattr(position, "symbol", None),
            strategy=getattr(
                getattr(setup, "strategy", None) or getattr(position, "strategy", None),
                "value",
                None,
            ),
            setup_id=setup_id,
            position_id=getattr(position, "position_id", None),
        )
        self.state.events.append(event)
        self.state.events = self.state.events[-500:]
        self.log.info(event_type, **event.model_dump(mode="json", exclude_none=True))
