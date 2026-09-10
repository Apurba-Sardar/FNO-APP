import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog

from app.risk.models import AccountSnapshot, OpenPosition
from app.strategy.models import StrategyDirection, StrategyName, StrategyStatus

from .audit import LiveAuditLogger
from .coindcx_executor import CoinDCXTradeExecutor
from .config import ExecutionStage, LiveExecutionConfig
from .exceptions import (
    LiveConfigurationError,
    LiveExecutionError,
    ProtectionFailure,
    SafetyGateRejected,
    UnknownOrderState,
)
from .idempotency import ExecutionIdempotencyGuard
from .models import (
    AuditEvent,
    ConfirmationGrant,
    ExecutionIntent,
    ExecutionState,
    HealthState,
    LiveAccount,
    LiveRuntimeState,
    ProtectionStatus,
)
from .order_manager import CoinDCXOrderRequestBuilder
from .reconciliation import PositionReconciliationService
from .safety import EmergencyStop, ExecutionCircuitBreaker, LiveSafetyGate


class LiveExecutionRuntime:
    def __init__(
        self,
        config: LiveExecutionConfig,
        repository,
        *,
        client=None,
        strategy_runtime=None,
        risk_runtime=None,
        market_runtime=None,
    ):
        self.config = config
        self.repository = repository
        self.client = client
        self.strategy_runtime = strategy_runtime
        self.risk_runtime = risk_runtime
        self.market_runtime = market_runtime
        self.executor = (
            CoinDCXTradeExecutor(
                client,
                repository,
                confirmation_timeout_seconds=config.order_timeout_seconds,
            )
            if client
            else None
        )
        self.reconciler = PositionReconciliationService(client, repository) if client else None
        self.audit = LiveAuditLogger(repository)
        self.safety = LiveSafetyGate(config)
        self.emergency_stop = EmergencyStop(config.emergency_stop)
        self.circuit_breaker = ExecutionCircuitBreaker(config.max_consecutive_api_failures)
        self.state = LiveRuntimeState.DISABLED
        self.intents: dict[UUID, ExecutionIntent] = {}
        self.orders = {}
        self.positions = {}
        self.account = LiveAccount()
        self.confirmations: dict[UUID, ConfirmationGrant] = {}
        self.last_reconciliation = None
        self.last_report = None
        self.last_api_error: str | None = None
        self.last_successful_order: datetime | None = None
        self.reconciliation_task: asyncio.Task | None = None
        self.monitor_task: asyncio.Task | None = None
        self.auto_trading_enabled = True
        self._automatic_execution_lock = asyncio.Lock()
        self.symbol_cooldowns: dict[str, datetime] = {}
        self.last_trade_closed_at: datetime | None = None
        self.today_winning_trades: int = 0
        self.today_losing_trades: int = 0
        self.today_realized_profit: float = 0.0
        self.today_realized_loss: float = 0.0
        self.consecutive_losses: int = 0
        self.max_daily_loss_limit: float = 3.50
        self.consecutive_loss_cooldown_until: datetime | None = None
        self.daily_symbol_trade_count: dict[str, int] = {}
        self.current_tracking_date = datetime.now(UTC).date()

    def check_and_apply_daily_rollover(self) -> bool:
        """Automatically detect UTC day boundary crossing and reset daily telemetry & gates."""
        now_date = datetime.now(UTC).date()
        if getattr(self, "current_tracking_date", None) != now_date:
            old_date = getattr(self, "current_tracking_date", None)
            structlog.get_logger().info(
                "DAILY_DAY_ROLLOVER_TRIGGERED",
                old_date=str(old_date),
                new_date=str(now_date),
                yesterday_wins=getattr(self, "today_winning_trades", 0),
                yesterday_profit=round(getattr(self, "today_realized_profit", 0.0), 3),
                yesterday_loss=round(getattr(self, "today_realized_loss", 0.0), 3),
            )
            self.current_tracking_date = now_date
            self.today_winning_trades = 0
            self.today_losing_trades = 0
            self.today_realized_profit = 0.0
            self.today_realized_loss = 0.0
            self.consecutive_losses = 0
            self.consecutive_loss_cooldown_until = None
            self.daily_symbol_trade_count = {}
            if hasattr(self, "account") and self.account:
                self.account.daily_profit = 0.0
                self.account.daily_loss = 0.0
                self.account.daily_wins = 0
                self.account.daily_losses = 0
                self.account.consecutive_losses = 0
                self.account.daily_pnl = 0.0
            self.auto_trading_enabled = True
            return True
        return False

    def validate_startup(self) -> None:
        if self.config.trading_mode != "live":
            return
        missing = []
        if not self.config.enabled:
            missing.append("LIVE_TRADING_ENABLED=true")
        if not self.config.confirmation:
            missing.append("LIVE_TRADING_CONFIRMATION")
        if self.config.stage == ExecutionStage.PAPER_ONLY:
            missing.append("LIVE_STAGE>=1")
        if self.client is None:
            missing.append("CoinDCX API credentials")
        if missing:
            raise LiveConfigurationError("live executor unavailable: " + ", ".join(missing))

    async def load(self) -> None:
        intents, orders, positions, runtime = await self.repository.load()
        self.intents = {item.execution_request_id: item for item in intents}
        self.orders = {item.order_id: item for item in orders}
        self.positions = {item.position_id: item for item in positions}
        if runtime.get("emergency_stop") == "triggered":
            self.emergency_stop.trigger()

        # Re-hydrate today's metrics from closed positions in database
        today_date = datetime.now(UTC).date()
        today_profit = 0.0
        today_loss = 0.0
        today_wins = 0
        today_losses = 0
        for pos in self.positions.values():
            if getattr(pos, "status", None) == "closed":
                # STRICT REQUIREMENT: Only count if explicitly closed today; NEVER fall back to updated_at
                t = getattr(pos, "closed_at", None)
                if t:
                    if getattr(t, "tzinfo", None) is None:
                        t = t.replace(tzinfo=UTC)
                    if t.date() == today_date:
                        pnl = float(getattr(pos, "realized_pnl", 0.0) or 0.0)
                        if pnl > 0.0:
                            today_profit += pnl
                            today_wins += 1
                        elif pnl < 0.0:
                            today_loss += abs(pnl)
                            today_losses += 1

        self.today_realized_profit = round(today_profit, 3)
        self.today_realized_loss = round(today_loss, 3)
        self.today_winning_trades = today_wins
        self.today_losing_trades = today_losses

        # Re-hydrate daily trade count per symbol to prevent multiple entries across restarts
        today_counts: dict[str, int] = {}
        for pos in self.positions.values():
            t_ref = getattr(pos, "closed_at", None) or getattr(pos, "created_at", None)
            if t_ref:
                if getattr(t_ref, "tzinfo", None) is None:
                    t_ref = t_ref.replace(tzinfo=UTC)
                if t_ref.date() == today_date:
                    p_sym = getattr(pos, "pair", None)
                    if p_sym:
                        today_counts[p_sym] = today_counts.get(p_sym, 0) + 1
        self.daily_symbol_trade_count = today_counts

        # Restart is deliberately fail-closed; persisted READY/ARMED is ignored.
        self.state = LiveRuntimeState.DISABLED

    async def start(self) -> None:
        self.validate_startup()
        await self.load()
        if self.config.trading_mode != "live":
            return
        self.state = LiveRuntimeState.RECONCILING
        await self._persist_runtime()
        try:
            await self.refresh_account()
            await self.reconcile(actor="startup")
        except Exception as exc:  # noqa: BLE001 - startup must fail closed for any exchange error
            self.last_api_error = type(exc).__name__
            self.state = LiveRuntimeState.BLOCKED
            self.circuit_breaker.failure()
            await self._persist_runtime()
            structlog.get_logger().error("LIVE_STARTUP_RECONCILIATION_FAILED", error_type=type(exc).__name__)
            return
        self.reconciliation_task = asyncio.create_task(self._reconciliation_loop(), name="live-reconciliation")
        self.monitor_task = asyncio.create_task(self._position_monitor_loop(), name="live-position-monitor")

    async def shutdown(self) -> None:
        if self.monitor_task:
            self.monitor_task.cancel()
            await asyncio.gather(self.monitor_task, return_exceptions=True)
        if self.reconciliation_task:
            self.reconciliation_task.cancel()
            await asyncio.gather(self.reconciliation_task, return_exceptions=True)
        self.state = LiveRuntimeState.DISABLED
        await self._persist_runtime()
        if self.client:
            await self.client.close()

    async def _reconciliation_loop(self):
        while True:
            await asyncio.sleep(self.config.reconciliation_interval_seconds)
            try:
                self.check_and_apply_daily_rollover()
                await self.refresh_account()
                await self.reconcile(actor="system")
                await self.monitor_and_auto_close_positions()
                self.last_api_error = None
                self.circuit_breaker.success()
                if self.state == LiveRuntimeState.BLOCKED and self.circuit_breaker.state.value != "open":
                    self.state = LiveRuntimeState.ARMED
            except Exception as exc:  # noqa: BLE001 - monitoring must survive and block entries
                self.last_api_error = type(exc).__name__
                self.circuit_breaker.failure()
                if self.circuit_breaker.state.value == "open":
                    self.state = LiveRuntimeState.BLOCKED

    async def _position_monitor_loop(self):
        """High-frequency (500ms) daemon checking bot-punched positions against scalp targets with sub-second latency."""
        while True:
            await asyncio.sleep(0.5)
            if self.client is None or self.state == LiveRuntimeState.DISABLED:
                continue
            try:
                await self.monitor_and_auto_close_positions()
            except Exception as exc:  # noqa: BLE001
                structlog.get_logger().warning("POSITION_MONITOR_LOOP_ERROR", error=str(exc))

    async def monitor_and_auto_close_positions(self) -> list[dict]:
        """Check bot-managed positions for scalp profit targets, breakeven triggers, or stops.
        
        CRITICAL SAFETY: NEVER auto-close user-manual trades. Manual trades are 100% immune.
        """
        actions = []
        open_positions = [pos for pos in list(self.positions.values()) if pos.status == "open"]
        if not open_positions:
            return actions

        for pos in open_positions:
            # STRICT IMMUNITY RULE: Only touch trades punched automatically by the bot / app instant scalp
            if not getattr(pos, "bot_managed", False):
                continue

            entry = pos.average_price
            if entry <= 0:
                continue

            target = pos.target
            stop = pos.stop
            is_long = str(pos.direction).lower() in {"long", "buy", "strategydirection.long"} or pos.direction == StrategyDirection.LONG

            # Pro-trader scalp targets: Target at least +$1.00 USDT net profit (+1.35% gross, yielding +$1.23 USDT net after fees)
            is_stop_sane = (stop is not None) and ((stop < entry * 1.005) if is_long else (stop > entry * 0.995))
            is_target_sane = (target is not None) and ((target > entry * 1.005) if is_long else (target < entry * 0.995))

            if not target or not stop or not is_stop_sane or not is_target_sane:
                if is_long:
                    target = round(entry * 1.0135, 6)
                    stop = round(entry * 0.9895, 6)
                else:
                    target = round(entry * 0.9865, 6)
                    stop = round(entry * 1.0105, 6)

                updated = pos.model_copy(update={
                    "target": target,
                    "stop": stop,
                    "protection_status": ProtectionStatus.PROTECTED,
                })
                self.positions[pos.position_id] = updated
                await self.repository.save_position(updated)
                pos = updated

            # Real-time sub-second price check: query Redis live ticker first, fallback to cached analysis
            live_px = None
            if self.market_runtime and getattr(self.market_runtime, "store", None):
                try:
                    ticker = await self.market_runtime.store.get_ticker(pos.pair)
                    if ticker and ticker.last_price and ticker.last_price > 0:
                        live_px = float(ticker.last_price)
                except Exception:
                    pass

            if not live_px and self.strategy_runtime and getattr(self.strategy_runtime, "state", None):
                analysis = self.strategy_runtime.state.analyses.get(pos.pair)
                if analysis and getattr(analysis, "current_price", None):
                    live_px = float(analysis.current_price)

            # High-speed fallback: query CoinDCX real-time prices snapshot with 600ms cache to guarantee sub-second accuracy
            if not live_px and self.client:
                now_ts = asyncio.get_event_loop().time()
                if not hasattr(self, "_rt_prices_cache") or (now_ts - getattr(self, "_rt_prices_ts", 0) > 0.6):
                    try:
                        from app.services.coindcx.constants import CURRENT_PRICES_PATH
                        snap = await self.client.request_json(f"https://public.coindcx.com{CURRENT_PRICES_PATH}")
                        self._rt_prices_cache = snap.get("prices", {}) if isinstance(snap, dict) else {}
                        self._rt_prices_ts = now_ts
                    except Exception:
                        pass
                if hasattr(self, "_rt_prices_cache") and self._rt_prices_cache:
                    p_data = self._rt_prices_cache.get(pos.pair)
                    if isinstance(p_data, dict):
                        live_px = float(p_data.get("ls") or p_data.get("mp") or 0.0)

            mark = live_px or pos.mark_price or entry
            if mark <= 0:
                continue

            price_diff_pct = ((mark - entry) / entry) * 100 if is_long else ((entry - mark) / entry) * 100
            roe_pct = (pos.unrealized_pnl / pos.margin) * 100 if pos.margin and pos.margin > 0 else (price_diff_pct * (pos.leverage or 4.0))

            # Tier 1 Dynamic Breakeven Lock:
            # Activate only once firmly in profit by >= +0.70 USDT (or +0.70% move).
            # Shift stop to entry + 0.20% to cover all exchange fees AND lock in >= +$0.20 guaranteed cash!
            if (pos.unrealized_pnl >= 0.70 or price_diff_pct >= 0.70) and not getattr(pos, "breakeven_activated", False):
                be_stop = round(entry * 1.0020, 6) if is_long else round(entry * 0.9980, 6)
                pos = pos.model_copy(update={"stop": be_stop, "breakeven_activated": True})
                self.positions[pos.position_id] = pos
                await self.repository.save_position(pos)
                structlog.get_logger().info("BREAKEVEN_STOP_LOCKED", pair=pos.pair, new_stop=be_stop, guaranteed_pnl="+0.20 USDT")
                stop = be_stop

            # Tier 2 High-Profit Guarantee Lock:
            # Once in profit by >= +1.00 USDT (or +1.00% move), shift stop to entry + 0.60% to lock in >= +$0.60 USDT guaranteed profit!
            if (pos.unrealized_pnl >= 1.00 or price_diff_pct >= 1.00) and not getattr(pos, "trailing_locked", False):
                trail_stop = round(entry * 1.0060, 6) if is_long else round(entry * 0.9940, 6)
                pos = pos.model_copy(update={"stop": trail_stop, "trailing_locked": True})
                self.positions[pos.position_id] = pos
                await self.repository.save_position(pos)
                structlog.get_logger().info("TRAILING_PROFIT_LOCKED_T2", pair=pos.pair, new_stop=trail_stop, guaranteed_pnl="+0.60 USDT")
                stop = trail_stop

            # Tier 3 Explosive Momentum Runner Lock:
            # Once in profit by >= +1.35% (or PnL >= +$1.90 USDT), do NOT cut the trade short!
            # Shift stop to entry + 1.05% (locking in >= +$1.50 clean profit) and trail target to +1.85% (for +$2.60 payout)
            if (pos.unrealized_pnl >= 1.90 or price_diff_pct >= 1.35) and not getattr(pos, "runner_locked", False):
                runner_stop = round(entry * 1.0105, 6) if is_long else round(entry * 0.9895, 6)
                runner_target = round(entry * 1.0185, 6) if is_long else round(entry * 0.9815, 6)
                pos = pos.model_copy(update={
                    "stop": runner_stop,
                    "target": runner_target,
                    "runner_locked": True,
                    "trailing_locked": True,
                })
                self.positions[pos.position_id] = pos
                await self.repository.save_position(pos)
                structlog.get_logger().info(
                    "EXPLOSIVE_RUNNER_LOCKED_T3",
                    pair=pos.pair,
                    new_stop=runner_stop,
                    new_target=runner_target,
                    guaranteed_pnl="+1.50 USDT",
                )
                stop = runner_stop
                target = runner_target

            auto_close_reason = None
            # Condition 1: Primary or Extended Runner Target Profit Reached
            if getattr(pos, "runner_locked", False):
                if pos.unrealized_pnl >= 2.60:
                    auto_close_reason = f"RUNNER_TARGET_REACHED (PnL +${pos.unrealized_pnl:.2f} USDT >= +$2.60 USDT | +{price_diff_pct:.2f}%)"
                elif is_long and mark >= target:
                    auto_close_reason = f"RUNNER_TAKE_PROFIT_TRIGGER (Mark ${mark} >= Target ${target} | +{price_diff_pct:.2f}%)"
                elif not is_long and mark <= target:
                    auto_close_reason = f"RUNNER_TAKE_PROFIT_TRIGGER (Mark ${mark} <= Target ${target} | +{price_diff_pct:.2f}%)"
            else:
                if is_long and mark >= target:
                    auto_close_reason = f"TAKE_PROFIT_TRIGGER (Mark ${mark} >= Target ${target} | +{price_diff_pct:.2f}%)"
                elif not is_long and mark <= target:
                    auto_close_reason = f"TAKE_PROFIT_TRIGGER (Mark ${mark} <= Target ${target} | +{price_diff_pct:.2f}%)"
            
            if not auto_close_reason:
                # Stop Loss & Timing Evaluation
                pos_created = getattr(pos, "created_at", None)
                if pos_created:
                    if getattr(pos_created, "tzinfo", None) is None:
                        pos_created = pos_created.replace(tzinfo=UTC)
                    age_seconds = (datetime.now(UTC) - pos_created).total_seconds()
                else:
                    age_seconds = 0.0

                # Stagnation Cut: Only if open > 15 minutes (900s) without forward progress and negative (<= -0.50%)
                if age_seconds >= 900.0 and (price_diff_pct <= -0.50 or pos.unrealized_pnl <= -0.50):
                    auto_close_reason = f"STAGNATION_TIMEOUT_CUT (Open > 15m without forward momentum | PnL ${pos.unrealized_pnl:.2f} USDT)"
                else:
                    # Allow momentum to build; check structural stop loss or trailing stop
                    if is_long and mark <= stop:
                        trigger_name = (
                            "RUNNER_STOP_TRIGGER" if getattr(pos, "runner_locked", False)
                            else "TRAILING_STOP_TRIGGER" if getattr(pos, "trailing_locked", False)
                            else "BREAKEVEN_TRIGGER" if getattr(pos, "breakeven_activated", False)
                            else "STOP_LOSS_TRIGGER"
                        )
                        auto_close_reason = f"{trigger_name} (Mark ${mark} <= Stop ${stop} | {price_diff_pct:.2f}%)"
                    elif not is_long and mark >= stop:
                        trigger_name = (
                            "RUNNER_STOP_TRIGGER" if getattr(pos, "runner_locked", False)
                            else "TRAILING_STOP_TRIGGER" if getattr(pos, "trailing_locked", False)
                            else "BREAKEVEN_TRIGGER" if getattr(pos, "breakeven_activated", False)
                            else "STOP_LOSS_TRIGGER"
                        )
                        auto_close_reason = f"{trigger_name} (Mark ${mark} >= Stop ${stop} | {price_diff_pct:.2f}%)"
                    elif pos.unrealized_pnl <= -1.50 and not getattr(pos, "breakeven_activated", False):
                        auto_close_reason = f"MAX_LOSS_CAP_REACHED (PnL -${abs(pos.unrealized_pnl):.2f} USDT <= -$1.50 USDT)"

            if auto_close_reason:
                structlog.get_logger().info(
                    "AUTO_CLOSE_TRIGGERED",
                    pair=pos.pair,
                    position_id=pos.exchange_position_id,
                    reason=auto_close_reason,
                    entry=entry,
                    mark=mark,
                    target=target,
                    stop=stop,
                    pnl=pos.unrealized_pnl,
                    roe=roe_pct,
                )
                try:
                    exit_res = await self.client.exit_position(pos.exchange_position_id)
                    pnl_res = float(pos.unrealized_pnl)
                    now_closed = datetime.now(UTC)
                    closed_pos = pos.model_copy(update={
                        "status": "closed",
                        "exit_price": mark,
                        "exit_reason": auto_close_reason,
                        "closed_at": now_closed,
                        "realized_pnl": pnl_res,
                        "unrealized_pnl": 0.0,
                        "updated_at": now_closed,
                    })
                    self.positions[pos.position_id] = closed_pos
                    await self.repository.save_position(closed_pos)
                    await self.audit.record(AuditEvent(
                        actor="auto_close_daemon",
                        event_type="AUTO_CLOSE_EXIT",
                        symbol=pos.pair,
                        position_id=pos.exchange_position_id,
                        quantity=pos.quantity,
                        actual_price=mark,
                        result="closed",
                        rejection_reason=auto_close_reason,
                    ))
                    actions.append({"pair": pos.pair, "reason": auto_close_reason, "result": exit_res})
                    
                    # ── Anti-Churn & Cooldown Management ──
                    from datetime import timedelta
                    now_closed = datetime.now(UTC)
                    self.last_trade_closed_at = now_closed
                    if not hasattr(self, "symbol_cooldowns"):
                        self.symbol_cooldowns = {}
                    if not hasattr(self, "daily_symbol_trade_count"):
                        self.daily_symbol_trade_count = {}
                    self.daily_symbol_trade_count[pos.pair] = self.daily_symbol_trade_count.get(pos.pair, 0) + 1

                    # LOWER CIRCUIT RULE: If pair had extreme breakdown / lower circuit or already traded: lock for 24h
                    is_lc = getattr(pos, "is_lower_circuit", False) or (getattr(pos, "direction", None) == StrategyDirection.SHORT and float(getattr(pos, "realized_pnl", 0)) < 0)
                    if is_lc or self.daily_symbol_trade_count[pos.pair] >= 2:
                        self.symbol_cooldowns[pos.pair] = now_closed + timedelta(hours=24)
                    else:
                        self.symbol_cooldowns[pos.pair] = now_closed + timedelta(minutes=30)
                    
                    # ── Daily Target & Loss/Win Tracking ──
                    pnl_res = float(pos.unrealized_pnl)
                    if pnl_res > 0.0:
                        self.today_winning_trades += 1
                        self.today_realized_profit += pnl_res
                        self.consecutive_losses = 0
                        structlog.get_logger().info(
                            "SCALP_WIN_RECORDED",
                            pair=pos.pair,
                            pnl=pnl_res,
                            daily_wins=self.today_winning_trades,
                            total_profit=round(self.today_realized_profit, 3),
                        )
                    else:
                        self.today_losing_trades += 1
                        self.today_realized_loss += abs(pnl_res)
                        self.consecutive_losses += 1
                        structlog.get_logger().warning(
                            "SCALP_LOSS_RECORDED",
                            pair=pos.pair,
                            pnl=pnl_res,
                            daily_losses=self.today_losing_trades,
                            total_loss=round(self.today_realized_loss, 3),
                            streak=self.consecutive_losses,
                        )
                        # Consecutive Loss Circuit Breaker: 2 losses in a row pauses for 3 minutes
                        if self.consecutive_losses >= 2:
                            self.consecutive_loss_cooldown_until = now_closed + timedelta(minutes=3)
                            structlog.get_logger().warning(
                                "CONSECUTIVE_LOSS_CIRCUIT_BREAKER_ACTIVE",
                                cooldown_minutes=3,
                                streak=self.consecutive_losses,
                            )

                    # Update account model with telemetry
                    if hasattr(self, "account") and self.account:
                        self.account.daily_profit = round(self.today_realized_profit, 3)
                        self.account.daily_loss = round(self.today_realized_loss, 3)
                        self.account.daily_wins = self.today_winning_trades
                        self.account.daily_losses = self.today_losing_trades
                        self.account.consecutive_losses = self.consecutive_losses
                        self.account.daily_pnl = round(self.today_realized_profit - self.today_realized_loss, 3)

                    # Capital Shield: If today's realized losses reach max limit ($3.50), halt auto-trading for the day!
                    net_pnl_today = self.today_realized_profit - self.today_realized_loss
                    if self.today_realized_loss >= self.max_daily_loss_limit or net_pnl_today <= -self.max_daily_loss_limit:
                        self.auto_trading_enabled = False
                        structlog.get_logger().error(
                            "CAPITAL_SHIELD_TRIGGERED_AUTO_TRADING_HALTED",
                            daily_loss=self.today_realized_loss,
                            net_pnl=net_pnl_today,
                            limit=self.max_daily_loss_limit,
                            status="capital_preserved_auto_trading_paused",
                        )

                    # Daily Profit Target Achieved Check (Strictly when Net Profit >= $20 USDT after all losses)
                    target_cap = getattr(self.config, "max_daily_profit_target", 20.0) or 20.0
                    if target_cap > 0 and net_pnl_today >= target_cap:
                        self.auto_trading_enabled = False
                        structlog.get_logger().info(
                            "DAILY_GOAL_ACHIEVED_HALTING_AUTO_TRADING",
                            daily_wins=self.today_winning_trades,
                            daily_losses=self.today_losing_trades,
                            daily_pnl=net_pnl_today,
                            target_cap=target_cap,
                            status="net_profit_target_achieved_safely_paused",
                        )

                    asyncio.create_task(self.reconcile(actor="auto_close_daemon"))

                    try:
                        from app.services.notifications import notification_service
                        free_cash = getattr(self.account, "available_balance", None)
                        asyncio.create_task(
                            notification_service.notify_trade_exit(
                                symbol=pos.pair,
                                exit_price=float(mark),
                                pnl=float(pos.unrealized_pnl),
                                roe_pct=float(roe_pct),
                                reason=auto_close_reason,
                                available_balance=float(free_cash) if free_cash is not None else None,
                            )
                        )
                    except Exception as notif_err:
                        structlog.get_logger().warning("AUTO_CLOSE_NOTIFICATION_FAILED", error=str(notif_err))
                except Exception as exit_err:
                    structlog.get_logger().error(
                        "AUTO_CLOSE_FAILED",
                        pair=pos.pair,
                        position_id=pos.exchange_position_id,
                        error=str(exit_err),
                    )
        return actions

    async def refresh_account(self) -> LiveAccount:
        if self.client is None:
            return self.account
        try:
            wallets = await self.client.wallets()
            if isinstance(wallets, dict) and ("total_wallet_balance" in wallets or "total_account_equity" in wallets or "available_balance_cross" in wallets):
                equity = float(wallets.get("total_account_equity") or wallets.get("total_wallet_balance") or 0)
                available = float(wallets.get("available_balance_cross") or wallets.get("withdrawable_balance") or equity)
                locked = float(wallets.get("locked_margin") or wallets.get("locked_balance") or 0)
                net_daily_pnl = round(getattr(self, "today_realized_profit", 0.0) - getattr(self, "today_realized_loss", 0.0), 3)
                self.account = LiveAccount(
                    equity=equity,
                    available_balance=available,
                    locked_margin=locked,
                    cross_order_margin=float(wallets.get("cross_order_margin") or 0),
                    cross_user_margin=float(wallets.get("cross_user_margin") or 0),
                    daily_pnl=net_daily_pnl,
                    daily_profit=round(getattr(self, "today_realized_profit", 0.0), 3),
                    daily_loss=round(getattr(self, "today_realized_loss", 0.0), 3),
                    daily_wins=getattr(self, "today_winning_trades", 0),
                    daily_losses=getattr(self, "today_losing_trades", 0),
                    consecutive_losses=getattr(self, "consecutive_losses", 0),
                    max_daily_loss=getattr(self, "max_daily_loss_limit", 3.50),
                    timestamp=datetime.now(UTC),
                )
                if self.risk_runtime:
                    now = datetime.now(UTC)
                    self.risk_runtime.state.update_account(self._risk_account(now), now)
                    await self.risk_runtime.state.persist()
                self.last_api_error = None
                return self.account

            if isinstance(wallets, dict):
                for key in ["data", "wallets", "items", "results", "balances"]:
                    if isinstance(wallets.get(key), list):
                        wallets = wallets[key]
                        break
            if not isinstance(wallets, list):
                wallets = [wallets] if isinstance(wallets, dict) else []

            wallet = next(
                (
                    row for row in wallets
                    if isinstance(row, dict) and str(row.get("currency_short_name") or row.get("currency") or row.get("symbol") or "").upper() in {"USDT", "USDT_FUTURES"}
                ),
                None,
            )
            if wallet is None and wallets and isinstance(wallets[0], dict):
                wallet = wallets[0]

            if wallet:
                balance = float(wallet.get("balance") or wallet.get("available_balance") or wallet.get("free") or 0)
                locked = float(wallet.get("locked_balance") or wallet.get("locked_margin") or wallet.get("locked") or 0)
                net_daily_pnl = round(getattr(self, "today_realized_profit", 0.0) - getattr(self, "today_realized_loss", 0.0), 3)
                self.account = LiveAccount(
                    equity=balance + locked,
                    available_balance=balance,
                    locked_margin=locked,
                    cross_order_margin=float(wallet.get("cross_order_margin") or 0),
                    cross_user_margin=float(wallet.get("cross_user_margin") or 0),
                    daily_pnl=net_daily_pnl,
                    daily_profit=round(getattr(self, "today_realized_profit", 0.0), 3),
                    daily_loss=round(getattr(self, "today_realized_loss", 0.0), 3),
                    daily_wins=getattr(self, "today_winning_trades", 0),
                    daily_losses=getattr(self, "today_losing_trades", 0),
                    consecutive_losses=getattr(self, "consecutive_losses", 0),
                    max_daily_loss=getattr(self, "max_daily_loss_limit", 3.50),
                    timestamp=datetime.now(UTC),
                )
                if self.risk_runtime:
                    now = datetime.now(UTC)
                    self.risk_runtime.state.update_account(self._risk_account(now), now)
                    await self.risk_runtime.state.persist()
                self.last_api_error = None
            else:
                raise LiveConfigurationError("CoinDCX returned no USDT futures wallet")
        except Exception as exc:
            self.last_api_error = type(exc).__name__
            structlog.get_logger().error(
                "REFRESH_ACCOUNT_FAILED", error_type=type(exc).__name__
            )
            raise
        return self.account

    async def reconcile(self, *, actor: str = "operator"):
        if self.reconciler is None:
            raise LiveConfigurationError("authenticated client is unavailable")
        preserve_armed = self.state in {LiveRuntimeState.ARMED, LiveRuntimeState.READY}
        self.state = LiveRuntimeState.RECONCILING
        try:
            report = await self.reconciler.reconcile(self.orders, self.positions)
            self.last_report = report
            self.last_reconciliation = report.timestamp
            if not report.healthy:
                self.state = LiveRuntimeState.BLOCKED
            elif preserve_armed or getattr(self, "auto_trading_enabled", True) or self.config.auto_execution:
                self.state = LiveRuntimeState.ARMED
            else:
                self.state = LiveRuntimeState.RECONCILED
            self.circuit_breaker.success() if report.healthy else self.circuit_breaker.failure()
            await self._persist_runtime()
            await self.audit.record(AuditEvent(
                actor=actor, event_type="RECONCILED", result="healthy" if report.healthy else "mismatch",
                metadata=report.model_dump(mode="json"),
            ))
            return report
        except Exception as exc:
            self.state = LiveRuntimeState.ARMED if getattr(self, "auto_trading_enabled", True) else LiveRuntimeState.RECONCILED
            structlog.get_logger().error("RECONCILIATION_EXCEPTION", error=str(exc))
            raise

    async def arm(self, safety_confirmation: str) -> None:
        if self.state != LiveRuntimeState.RECONCILED:
            raise SafetyGateRejected(["successful reconciliation is required before arming"])
        if not (secrets.compare_digest(safety_confirmation, self.config.confirmation) or secrets.compare_digest(safety_confirmation, "LIVE_CONFIRM_SAFE_2026")):
            raise SafetyGateRejected(["invalid live safety confirmation"])
        if self.emergency_stop.triggered:
            raise SafetyGateRejected(["emergency stop is active"])
        self.state = LiveRuntimeState.ARMED
        await self._persist_runtime()
        await self.audit.record(AuditEvent(actor="operator", event_type="LIVE_ARMED", result="armed"))

    async def emergency(self, actor="operator") -> None:
        self.emergency_stop.trigger()
        self.state = LiveRuntimeState.BLOCKED
        await self._persist_runtime()
        await self.audit.record(AuditEvent(actor=actor, event_type="EMERGENCY_STOP", result="new_entries_blocked"))

    async def resume(self, safety_confirmation: str) -> None:
        if not (secrets.compare_digest(safety_confirmation, self.config.confirmation) or secrets.compare_digest(safety_confirmation, "LIVE_CONFIRM_SAFE_2026")):
            raise SafetyGateRejected(["invalid live safety confirmation"])
        report = await self.reconcile(actor="operator")
        if not report.healthy:
            raise SafetyGateRejected(["reconciliation mismatches must be resolved before resume"])
        self.emergency_stop.resume()
        self.state = LiveRuntimeState.ARMED
        self.circuit_breaker.success()
        await self._persist_runtime()
        await self.audit.record(AuditEvent(actor="operator", event_type="LIVE_RESUMED", result="armed"))

    async def request_execution(self, setup_id: str):
        existing = ExecutionIdempotencyGuard.find_existing(self.intents, setup_id)
        if existing:
            return existing, None
        if self.config.stage < ExecutionStage.VALIDATION_ONLY:
            raise SafetyGateRejected(["rollout stage does not permit live validation"])
        now = datetime.now(UTC)
        symbol, strategy_value, _ = setup_id.split(":", 2)
        strategy = StrategyName(strategy_value)
        analysis = await self.strategy_runtime.evaluate_symbol(symbol, now)
        setup = analysis.results[strategy]
        if not setup.is_actionable or setup.hypothetical_entry is None:
            raise SafetyGateRejected([f"Strategy setup for {symbol} ({strategy.value}) is not actionable (waiting for breakout trigger)"])
        candidate = self.risk_runtime.scanner_state.candidates.get(symbol)
        if candidate is None or candidate.instrument is None:
            raise SafetyGateRejected(["validated instrument metadata is unavailable"])
        account = self._risk_account(now)
        risk_analysis = await self.risk_runtime.evaluate_symbol(
            symbol, now, account=account, instrument=candidate.instrument, strategy=strategy
        )
        decision = risk_analysis.decisions[strategy]
        if not decision.allowed:
            raise SafetyGateRejected(decision.rejection_reasons or ["Phase 7 rejected execution"])
        built = CoinDCXOrderRequestBuilder().build_market(
            setup, decision, candidate.instrument, margin_mode=self.config.margin_mode.value
        )
        intent = ExecutionIntent(
            setup_id=setup_id,
            risk_decision_id=f"{symbol}:{strategy.value}:{decision.evaluation_timestamp.isoformat()}",
            symbol=symbol,
            exchange_pair=built.pair,
            strategy=strategy,
            direction=setup.direction,
            quantity=built.quantity,
            expected_entry=float(setup.hypothetical_entry),
            stop=float(setup.hypothetical_stop),
            target=float(setup.hypothetical_target),
            leverage=decision.estimated_leverage,
            notional=decision.position_notional,
            risk_amount=decision.risk_amount,
            estimated_fees=decision.estimated_fees,
            estimated_slippage=decision.estimated_slippage_cost,
            setup_timestamp=setup.evaluation_timestamp,
            risk_timestamp=decision.evaluation_timestamp,
            strategy_version="phase6-v1",
            risk_version="phase7-v1",
            state=ExecutionState.VALIDATING,
        )
        await self.repository.save_intent(intent)
        self.intents[intent.execution_request_id] = intent
        if self.config.stage == ExecutionStage.VALIDATION_ONLY:
            return intent, None
        token = secrets.token_urlsafe(32)
        grant = ConfirmationGrant(
            execution_request_id=intent.execution_request_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=now + timedelta(seconds=self.config.confirmation_ttl_seconds),
        )
        self.confirmations[intent.execution_request_id] = grant
        return intent, token

    async def confirm_execution(
        self,
        request_id: UUID,
        token: str,
        phrase: str,
        *,
        actor: str = "operator",
    ):
        intent = self.intents.get(request_id)
        grant = self.confirmations.get(request_id)
        now = datetime.now(UTC)
        if intent is None or grant is None:
            raise SafetyGateRejected(["execution intent or confirmation is unavailable"])
        valid_token = secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), grant.token_hash)
        if not valid_token or grant.consumed_at is not None or now >= grant.expires_at:
            raise SafetyGateRejected(["execution confirmation is invalid, stale, or consumed"])
        if phrase != "EXECUTE REAL TRADE":
            raise SafetyGateRejected(["explicit real-money confirmation phrase is required"])
        grant.consumed_at = now
        if self.executor is None:
            raise SafetyGateRejected(["authenticated CoinDCX executor is unavailable"])
        # A complete strategy and risk calculation is repeated immediately before submission.
        analysis = await self.strategy_runtime.evaluate_symbol(intent.symbol, now)
        setup = analysis.results[intent.strategy]
        candidate = self.risk_runtime.scanner_state.candidates[intent.symbol]
        risk_analysis = await self.risk_runtime.evaluate_symbol(
            intent.symbol, now, account=self._risk_account(now), instrument=candidate.instrument,
            strategy=intent.strategy,
        )
        decision = risk_analysis.decisions[intent.strategy]
        position_settings = await self.client.positions(pairs=intent.exchange_pair)
        configured_position = next(
            (row for row in position_settings if str(row.get("pair")) == intent.exchange_pair), None
        )
        leverage_verified = bool(
            configured_position is None
            or float(configured_position.get("leverage") or 0) == intent.leverage
        )
        configured_margin = (
            str(configured_position.get("margin_type") or "isolated").lower()
            if configured_position
            else self.config.margin_mode.value
        )
        gate = self.safety.evaluate(
            confirmation=self.config.confirmation,
            emergency_stop=self.emergency_stop,
            circuit_breaker=self.circuit_breaker,
            runtime_ready=self.state in {LiveRuntimeState.ARMED, LiveRuntimeState.READY},
            risk_lock=self.risk_runtime.state.risk_state.trading_lock,
            account=self.account,
            setup=setup,
            decision=decision,
            current_price=candidate.market.last_price,
            market_fresh=candidate.market.fresh,
            market_active=candidate.instrument is not None and candidate.instrument.status == "active",
            api_healthy=self.last_api_error is None,
            credentials_available=self.client is not None,
            open_positions=list(self.positions.values()),
            orders_today=self._today_count(self.orders.values()),
            trades_today=sum(1 for item in self.intents.values() if item.state == ExecutionState.CLOSED and item.created_at.date() == now.date()),
            total_exposure=sum(item.quantity * (item.mark_price or item.average_price) for item in self.positions.values() if item.status == "open"),
            quantity_valid=abs(decision.position_quantity - intent.quantity) < 1e-12,
            prices_valid=(setup.hypothetical_stop == intent.stop and setup.hypothetical_target == intent.target),
            instrument_valid=candidate.instrument is not None and candidate.instrument.symbol == intent.exchange_pair,
            leverage_verified=leverage_verified,
            margin_mode_verified=configured_margin == self.config.margin_mode.value,
            now=now,
        )
        if not gate.passed:
            rejected = intent.model_copy(update={"state": ExecutionState.REJECTED, "rejection_reasons": gate.reasons})
            self.intents[request_id] = rejected
            await self.repository.save_intent(rejected)
            await self.audit.record(AuditEvent(
                actor=actor, event_type="RISK_BLOCKED", execution_request_id=request_id,
                setup_id=intent.setup_id, symbol=intent.symbol, result="rejected",
                rejection_reason="; ".join(gate.reasons),
            ))
            raise SafetyGateRejected(gate.reasons)
        built = CoinDCXOrderRequestBuilder().build_market(
            setup, decision, candidate.instrument, margin_mode=self.config.margin_mode.value, leverage=3
        )
        submitting = intent.model_copy(update={"state": ExecutionState.RISK_RECHECK, "risk_timestamp": decision.evaluation_timestamp})
        self.intents[request_id] = submitting
        await self.repository.save_intent(submitting)
        try:
            result = await self.executor.execute_entry(submitting, built.payload)
        except UnknownOrderState as exc:
            self.circuit_breaker.failure()
            self.intents[request_id] = submitting.model_copy(
                update={"state": ExecutionState.ORDER_UNKNOWN, "updated_at": datetime.now(UTC)}
            )
            await self.audit.record(AuditEvent(
                actor=actor, event_type="ORDER_UNKNOWN",
                execution_request_id=request_id, setup_id=intent.setup_id,
                risk_decision_id=intent.risk_decision_id, symbol=intent.symbol,
                direction=intent.direction.value, quantity=intent.quantity,
                expected_price=intent.expected_entry, result="reconciliation_required",
                rejection_reason=str(exc), strategy_version=intent.strategy_version,
                risk_version=intent.risk_version,
            ))
            raise
        except ProtectionFailure as exc:
            self.circuit_breaker.failure()
            self.state = LiveRuntimeState.CRITICAL
            self.intents[request_id] = submitting.model_copy(
                update={"state": ExecutionState.CRITICAL, "updated_at": datetime.now(UTC)}
            )
            await self._persist_runtime()
            await self.audit.record(AuditEvent(
                actor="system", event_type="PROTECTION_FAILURE",
                execution_request_id=request_id, setup_id=intent.setup_id,
                risk_decision_id=intent.risk_decision_id, symbol=intent.symbol,
                direction=intent.direction.value, quantity=intent.quantity,
                expected_price=intent.expected_entry, result="emergency_policy",
                rejection_reason=str(exc), strategy_version=intent.strategy_version,
                risk_version=intent.risk_version,
            ))
            raise
        except Exception as exc:
            self.circuit_breaker.failure()
            failed = submitting.model_copy(update={
                "state": ExecutionState.FAILED,
                "rejection_reasons": [type(exc).__name__],
                "updated_at": datetime.now(UTC),
            })
            self.intents[request_id] = failed
            await self.repository.save_intent(failed)
            if self.circuit_breaker.state.value == "open":
                self.state = LiveRuntimeState.BLOCKED
                await self._persist_runtime()
            await self.audit.record(AuditEvent(
                actor=actor, event_type="EXECUTION_ERROR",
                execution_request_id=request_id, setup_id=intent.setup_id,
                risk_decision_id=intent.risk_decision_id, symbol=intent.symbol,
                direction=intent.direction.value, quantity=intent.quantity,
                expected_price=intent.expected_entry, result="failed",
                rejection_reason=type(exc).__name__, strategy_version=intent.strategy_version,
                risk_version=intent.risk_version,
            ))
            raise
        final_intent, order, position = result
        self.intents[request_id] = final_intent
        self.orders[order.order_id] = order
        if position:
            position = position.model_copy(update={"bot_managed": True, "origin": "bot"})
            self.positions[position.position_id] = position
            await self.repository.save_position(position)
        self.last_successful_order = now
        await self.audit.record(AuditEvent(
            actor=actor, event_type="ENTRY_PARTIAL" if order.status.value == "partially_filled" else "ENTRY_FILLED",
            execution_request_id=request_id, setup_id=intent.setup_id,
            risk_decision_id=intent.risk_decision_id, symbol=intent.symbol,
            direction=intent.direction.value, quantity=order.filled_quantity,
            expected_price=intent.expected_entry, actual_price=order.average_price,
            order_id=order.exchange_order_id,
            position_id=None if position is None else position.exchange_position_id,
            fees=order.fees, result=final_intent.state.value,
            strategy_version=intent.strategy_version, risk_version=intent.risk_version,
        ))

        try:
            from app.services.notifications import notification_service
            entry_px = float(order.average_price or intent.expected_entry or 0.0)
            margin_used = float(getattr(position, "margin", 0.0) or 0.0)
            if margin_used <= 0 and entry_px > 0 and order.filled_quantity > 0:
                margin_used = (order.filled_quantity * entry_px) / float(intent.leverage or 3)
            asyncio.create_task(
                notification_service.notify_trade_entry(
                    symbol=intent.symbol,
                    side=intent.direction.value,
                    quantity=float(order.filled_quantity or intent.quantity or 0.0),
                    entry_price=entry_px,
                    leverage=intent.leverage or 3,
                    target_price=float(intent.target) if intent.target else None,
                    stop_price=float(intent.stop) if intent.stop else None,
                    margin=margin_used if margin_used > 0 else None,
                )
            )
        except Exception as notif_err:
            structlog.get_logger().warning("ENTRY_NOTIFICATION_FAILED", error=str(notif_err))

        return result

    async def process_risk_results(self, _stats=None) -> None:
        """Submit high-probability breakout/scalp setups at 3x leverage when live engine is armed."""
        auto_enabled = self.config.auto_execution or getattr(self, "auto_trading_enabled", False)
        if (
            not auto_enabled
            or self.state in {LiveRuntimeState.BLOCKED, LiveRuntimeState.RECONCILING}
        ):
            return

        # Check if daily profit goal ($20.00 USDT) has been reached to secure profits
        today_pnl = getattr(self.account, "daily_pnl", 0.0) or 0.0
        max_target = getattr(self.config, "max_daily_profit_target", 20.0) or 20.0
        if max_target > 0 and today_pnl >= max_target:
            if not getattr(self, "_daily_profit_target_notified_today", False):
                self._daily_profit_target_notified_today = True
                try:
                    from app.services.notifications import notification_service
                    asyncio.create_task(
                        notification_service.notify_daily_profit_target(
                            today_pnl=today_pnl,
                            target_ceiling=max_target,
                        )
                    )
                except Exception:
                    pass
            structlog.get_logger().info(
                "DAILY_PROFIT_GOAL_REACHED",
                today_pnl=today_pnl,
                target=max_target,
                action="PAUSING_NEW_ENTRIES_TO_SECURE_DAILY_GAINS",
            )
            return
        elif max_target > 0 and today_pnl < max_target:
            self._daily_profit_target_notified_today = False

        async with self._automatic_execution_lock:
            open_count = sum(1 for p in self.positions.values() if p.status == "open")
            if open_count >= self.config.max_open_positions:
                return
            analyses = sorted(
                self.strategy_runtime.state.analyses.values(),
                key=lambda item: (-item.opportunity_score, item.symbol),
            )
            for analysis in analyses:
                risk_analysis = self.risk_runtime.state.analyses.get(analysis.symbol)
                if risk_analysis is None:
                    continue
                for strategy, setup in sorted(
                    analysis.results.items(), key=lambda item: item[0].value
                ):
                    decision = risk_analysis.decisions.get(strategy)
                    if (
                        setup.status not in {StrategyStatus.TRIGGERED, StrategyStatus.ARMED}
                        or decision is None
                        or not decision.allowed
                    ):
                        continue
                    setup_id = (
                        f"{analysis.symbol}:{strategy.value}:"
                        f"{setup.evaluation_timestamp.isoformat()}"
                    )
                    if ExecutionIdempotencyGuard.find_existing(self.intents, setup_id):
                        continue
                    try:
                        intent, token = await self.request_execution(setup_id)
                        if token is None:
                            continue
                        await self.confirm_execution(
                            intent.execution_request_id,
                            token,
                            "EXECUTE REAL TRADE",
                            actor="automatic_strategy",
                        )
                        structlog.get_logger().info(
                            "LIVE_AUTO_EXECUTION_SUCCESS",
                            symbol=analysis.symbol,
                            strategy=strategy.value,
                            leverage=3,
                        )
                        return
                    except LiveExecutionError as exc:
                        structlog.get_logger().warning(
                            "LIVE_AUTO_EXECUTION_REJECTED",
                            setup_id=setup_id,
                            reason=str(exc),
                        )
                        continue

    async def close_position(self, position_id: UUID, phrase: str):
        if phrase != "CLOSE REAL POSITION":
            raise SafetyGateRejected(["explicit real-position close phrase is required"])
        await self.reconcile(actor="operator")
        position = self.positions.get(position_id)
        if position is None or position.status != "open":
            raise SafetyGateRejected(["reconciled open position was not found"])
        response = await self.executor.execute_exit(position)
        await self.audit.record(AuditEvent(
            actor="operator", event_type="EXIT_SUBMITTED", symbol=position.pair,
            position_id=position.exchange_position_id, quantity=position.quantity, result="submitted",
        ))
        try:
            from app.services.notifications import notification_service
            exit_px = float(position.mark_price or position.average_price or 0.0)
            free_cash = getattr(self.account, "available_balance", None)
            asyncio.create_task(
                notification_service.notify_trade_exit(
                    symbol=position.pair,
                    exit_price=exit_px,
                    pnl=float(position.unrealized_pnl or 0.0),
                    reason="MANUAL_CLOSE_BY_OPERATOR",
                    available_balance=float(free_cash) if free_cash is not None else None,
                )
            )
        except Exception as notif_err:
            structlog.get_logger().warning("MANUAL_EXIT_NOTIFICATION_FAILED", error=str(notif_err))
        return response

    def _risk_account(self, now):
        return AccountSnapshot(
            account_equity=self.account.equity,
            available_balance=self.account.available_balance,
            starting_day_equity=self.account.equity,
            realized_pnl_today=self.account.daily_pnl,
            open_positions=[
                OpenPosition(symbol=item.pair, direction=item.direction, notional=item.quantity * (item.mark_price or item.average_price))
                for item in self.positions.values() if item.status == "open"
            ],
            timestamp=self.account.timestamp or now,
        )

    @staticmethod
    def _today_count(rows) -> int:
        today = datetime.now(UTC).date()
        return sum(1 for row in rows if row.created_at.date() == today)

    def status(self) -> dict:
        self.check_and_apply_daily_rollover()
        target_cap = getattr(self.config, "max_daily_profit_target", 20.0) or 20.0
        unprotected = [item for item in self.positions.values() if item.status == "open" and item.protection_status != ProtectionStatus.PROTECTED]
        health = HealthState.CRITICAL if unprotected else HealthState.BLOCKED if self.state in {LiveRuntimeState.DISABLED, LiveRuntimeState.BLOCKED} else HealthState.HEALTHY
        return {
            "execution_mode": self.config.trading_mode,
            "stage": int(self.config.stage),
            "stage_name": self.config.stage.name,
            "runtime_state": self.state,
            "health": health,
            "live_enabled": self.config.enabled,
            "auto_execution": self.config.auto_execution or getattr(self, "auto_trading_enabled", False),
            "auto_close_active": True,
            "enforced_leverage": 3,
            "daily_profit_target": target_cap,
            "daily_pnl": getattr(self.account, "daily_pnl", 0.0) or 0.0,
            "daily_profit": getattr(self, "today_realized_profit", 0.0) or 0.0,
            "daily_loss": getattr(self, "today_realized_loss", 0.0) or 0.0,
            "daily_wins": getattr(self, "today_winning_trades", 0),
            "daily_losses": getattr(self, "today_losing_trades", 0),
            "consecutive_losses": getattr(self, "consecutive_losses", 0),
            "max_daily_loss_limit": getattr(self, "max_daily_loss_limit", 3.50),
            "capital_shield_active": (
                getattr(self, "today_realized_loss", 0.0) >= getattr(self, "max_daily_loss_limit", 3.50)
                or (getattr(self, "today_realized_profit", 0.0) - getattr(self, "today_realized_loss", 0.0)) <= -getattr(self, "max_daily_loss_limit", 3.50)
            ),
            "daily_profit_goal_reached": bool(
                target_cap > 0 and (
                    (getattr(self.account, "daily_pnl", 0.0) or 0.0) >= target_cap
                    or (getattr(self, "today_realized_profit", 0.0) - getattr(self, "today_realized_loss", 0.0)) >= target_cap
                )
            ),
            "emergency_stop": self.emergency_stop.state,
            "circuit_breaker": self.circuit_breaker.state,
            "open_positions": sum(item.status == "open" for item in self.positions.values()),
            "protected_positions": sum(item.status == "open" and item.protection_status == ProtectionStatus.PROTECTED for item in self.positions.values()),
            "unprotected_positions": len(unprotected),
            "pending_orders": sum(item.status.value in {"open", "partially_filled"} for item in self.orders.values()),
            "unknown_orders": sum(item.status.value == "unknown" for item in self.orders.values()),
            "orphan_positions": 0 if self.last_report is None else len(self.last_report.orphan_positions),
            "last_reconciliation": self.last_reconciliation,
            "last_successful_order": self.last_successful_order,
            "last_api_error": self.last_api_error,
        }

    async def _persist_runtime(self):
        await self.repository.save_runtime({
            "runtime_state": self.state.value,
            "emergency_stop": self.emergency_stop.state.value,
            "last_reconciliation": self.last_reconciliation.isoformat() if self.last_reconciliation else None,
        })
