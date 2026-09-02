from collections import Counter
from time import perf_counter

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import RiskConfig
from .context import RiskContextBuilder
from .daily_limits import daily_loss, trading_day
from .exceptions import RiskContextUnavailable
from .models import (
    AccountSnapshot,
    RiskDecision,
    RiskLockState,
    RiskState,
    RiskStatistics,
    SymbolRiskAnalysis,
)


class RiskStateStore:
    def __init__(self, redis: Redis | None, config: RiskConfig) -> None:
        self.redis = redis
        self.config = config
        self.risk_state = RiskState()
        self.analyses: dict[str, SymbolRiskAnalysis] = {}
        self.stats: RiskStatistics | None = None

    async def load(self) -> None:
        if self.redis is None:
            return
        try:
            state = await self.redis.get(self.config.state_key)
            decisions = await self.redis.hgetall(self.config.decisions_key)
            stats = await self.redis.get(f"{self.config.decisions_key}:stats")
            if state:
                self.risk_state = RiskState.model_validate_json(state)
            self.analyses = {
                key.decode() if isinstance(key, bytes) else key: SymbolRiskAnalysis.model_validate_json(value)
                for key, value in decisions.items()
            }
            if stats:
                self.stats = RiskStatistics.model_validate_json(stats)
        except (RedisError, ValueError) as exc:
            self.risk_state.trading_lock = RiskLockState.BLOCKED
            self.risk_state.block_reasons = ["risk state restore failed"]
            structlog.get_logger().error("RISK_STATE_RESTORE_FAILED", error=str(exc))

    def update_account(self, account: AccountSnapshot, evaluation_timestamp) -> None:
        day = trading_day(evaluation_timestamp, self.config.utc_day_boundary_hour)
        if self.risk_state.trading_day is not None and self.risk_state.trading_day != day:
            account = account.model_copy(
                update={
                    "starting_day_equity": account.account_equity,
                    "realized_pnl_today": 0,
                    "unrealized_pnl": 0,
                    "fees_today": 0,
                    "funding_today": 0,
                    "deposits_today": 0,
                    "withdrawals_today": 0,
                }
            )
        pnl, loss, percent = daily_loss(account, self.config)
        exposure = sum(
            item.notional
            for item in account.open_positions
            if item.status != "confirmed_closed"
        )
        exposure_percent = exposure / account.account_equity * 100 if account.account_equity else 0
        reasons = []
        account_age = (
            (evaluation_timestamp - account.timestamp).total_seconds()
            if account.timestamp is not None
            else None
        )
        if (
            account.account_equity is None
            or account.available_balance is None
            or account.available_balance <= 0
            or account_age is None
            or account_age < 0
            or account_age > self.config.max_account_data_age_seconds
        ):
            reasons.append("account data unavailable")
        if percent >= self.config.max_daily_loss_percent:
            reasons.append("daily loss limit reached")
        if account.consecutive_losses >= self.config.max_consecutive_losses and (
            account.consecutive_loss_reset_at is None
            or evaluation_timestamp < account.consecutive_loss_reset_at
        ):
            reasons.append("consecutive loss limit reached")
        if len([item for item in account.open_positions if item.status != "confirmed_closed"]) >= self.config.max_open_positions:
            reasons.append("open position limit reached")
        lock = RiskLockState.BLOCKED if reasons else RiskLockState.OPEN
        self.risk_state = RiskState(
            account=account,
            daily_pnl=pnl,
            daily_loss=loss,
            daily_loss_percent=percent,
            total_exposure=exposure,
            exposure_percent=exposure_percent,
            trading_lock=lock,
            block_reasons=reasons,
            trading_day=day,
            last_updated=evaluation_timestamp,
        )
        if lock == RiskLockState.BLOCKED:
            structlog.get_logger().warning(
                "RISK_TRADING_BLOCKED",
                reasons=reasons,
                timestamp=evaluation_timestamp.isoformat(),
            )

    async def persist(self) -> None:
        if self.redis is None:
            return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(self.config.state_key, self.risk_state.model_dump_json())
                pipe.delete(self.config.decisions_key)
                if self.analyses:
                    pipe.hset(
                        self.config.decisions_key,
                        mapping={key: value.model_dump_json() for key, value in self.analyses.items()},
                    )
                if self.stats:
                    pipe.set(
                        f"{self.config.decisions_key}:stats",
                        self.stats.model_dump_json(),
                    )
                await pipe.execute()
        except RedisError as exc:
            self.risk_state.trading_lock = RiskLockState.BLOCKED
            self.risk_state.block_reasons = ["risk state persistence failed"]
            structlog.get_logger().error("RISK_STATE_PERSIST_FAILED", error=str(exc))


class RiskRuntime:
    def __init__(self, scanner_state, strategy_state, state: RiskStateStore, engine, config: RiskConfig) -> None:
        self.scanner_state = scanner_state
        self.strategy_state = strategy_state
        self.state = state
        self.engine = engine
        self.config = config
        self.context_builder = RiskContextBuilder()

    async def evaluate_symbol(
        self,
        symbol: str,
        evaluation_timestamp,
        *,
        account: AccountSnapshot | None = None,
        instrument=None,
        strategy=None,
        persist_account: bool = False,
    ) -> SymbolRiskAnalysis:
        analysis = self.strategy_state.analyses.get(symbol)
        candidate = self.scanner_state.candidates.get(symbol)
        if analysis is None or candidate is None:
            raise RiskContextUnavailable(f"risk context not found for {symbol}")
        selected = (
            [analysis.results[strategy]]
            if strategy is not None
            else [analysis.best_setup]
            if analysis.best_setup is not None
            else list(analysis.results.values())
        )
        account_snapshot = account or self.state.risk_state.account
        if persist_account and account is not None:
            self.state.update_account(account, evaluation_timestamp)
        decisions = {}
        for setup in selected:
            context = self.context_builder.build(
                analysis,
                setup,
                candidate,
                account_snapshot,
                evaluation_timestamp,
                instrument,
            )
            decisions[setup.strategy] = self.engine.evaluate(context)
        return SymbolRiskAnalysis(
            symbol=symbol,
            evaluation_timestamp=evaluation_timestamp,
            decisions=decisions,
        )

    async def evaluate_all(self, source_stats=None, *, evaluation_timestamp=None, account=None, limit=None, persist_account=False) -> RiskStatistics:
        from datetime import UTC, datetime

        timestamp = evaluation_timestamp or getattr(source_stats, "evaluated_at", None) or datetime.now(UTC)
        if persist_account and account is not None:
            self.state.update_account(account, timestamp)
        started = perf_counter()
        symbols = sorted(self.strategy_state.analyses)[: limit or 500]
        analyses = []
        for symbol in symbols:
            try:
                analyses.append(
                    await self.evaluate_symbol(
                        symbol,
                        timestamp,
                        account=account,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - risk batch isolates each symbol
                structlog.get_logger().error(
                    "RISK_SYMBOL_ERROR",
                    symbol=symbol,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
        decisions: list[RiskDecision] = [
            decision for analysis in analyses for decision in analysis.decisions.values()
        ]
        rejection_counts = Counter(
            reason for decision in decisions for reason in decision.rejection_reasons
        )
        stats = RiskStatistics(
            evaluated_at=timestamp,
            setups_evaluated=len(decisions),
            approved=sum(item.allowed for item in decisions),
            rejected=sum(not item.allowed for item in decisions),
            warning=sum(item.status.value == "warning" for item in decisions),
            status_counts=dict(Counter(item.status.value for item in decisions)),
            rejection_counts=dict(rejection_counts),
            duration_ms=(perf_counter() - started) * 1000,
        )
        self.state.analyses = {item.symbol: item for item in analyses}
        self.state.stats = stats
        await self.state.persist()
        return stats
