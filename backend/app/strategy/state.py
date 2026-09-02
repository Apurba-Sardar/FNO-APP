from collections import Counter
from time import perf_counter

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import StrategyConfig
from .exceptions import StrategyContextUnavailable
from .lifecycle import apply_lifecycle
from .models import StrategyStatistics, SymbolStrategyAnalysis


class StrategyState:
    def __init__(self, redis: Redis | None, config: StrategyConfig) -> None:
        self.redis = redis
        self.config = config
        self.analyses: dict[str, SymbolStrategyAnalysis] = {}
        self.stats: StrategyStatistics | None = None

    async def load(self) -> None:
        if self.redis is None:
            return
        try:
            rows = await self.redis.hgetall("strategies:current")
            stats = await self.redis.get("strategies:stats")
            self.analyses = {
                key.decode() if isinstance(key, bytes) else key: SymbolStrategyAnalysis.model_validate_json(value)
                for key, value in rows.items()
            }
            if stats:
                self.stats = StrategyStatistics.model_validate_json(stats)
        except (RedisError, ValueError) as exc:
            structlog.get_logger().warning("STRATEGY_STATE_RESTORE_FAILED", error=str(exc))

    async def replace(self, analyses: list[SymbolStrategyAnalysis], stats: StrategyStatistics) -> None:
        self.analyses = {item.symbol: item for item in analyses}
        self.stats = stats
        if self.redis is None:
            return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.delete("strategies:current")
                if analyses:
                    pipe.hset("strategies:current", mapping={item.symbol: item.model_dump_json() for item in analyses})
                    pipe.expire("strategies:current", self.config.state_ttl_seconds)
                pipe.setex("strategies:stats", self.config.state_ttl_seconds, stats.model_dump_json())
                await pipe.execute()
        except RedisError as exc:
            structlog.get_logger().warning("STRATEGY_STATE_REDIS_UNAVAILABLE", error=str(exc))


class StrategyRuntime:
    def __init__(self, scanner_state, opportunity_state, state: StrategyState, engine, config: StrategyConfig, on_completed=None) -> None:
        self.scanner_state = scanner_state
        self.opportunity_state = opportunity_state
        self.state = state
        self.engine = engine
        self.config = config
        self.on_completed = on_completed

    async def evaluate_symbol(self, symbol: str, evaluation_timestamp) -> SymbolStrategyAnalysis:
        opportunity = self.opportunity_state.opportunities.get(symbol)
        candidate = self.scanner_state.candidates.get(symbol)
        if opportunity is None or candidate is None:
            raise StrategyContextUnavailable(f"strategy context not found for {symbol}")
        current = self.engine.evaluate(opportunity, candidate, evaluation_timestamp)
        current = apply_lifecycle(self.state.analyses.get(symbol), current)
        return current

    async def evaluate_all(self, source_stats=None, *, evaluation_timestamp=None, limit=None) -> StrategyStatistics:
        from datetime import UTC, datetime

        started = perf_counter()
        timestamp = evaluation_timestamp or getattr(source_stats, "calculated_at", None) or datetime.now(UTC)
        maximum = limit or self.config.maximum_evaluated_symbols
        opportunities = sorted(
            (item for item in self.opportunity_state.opportunities.values() if item.eligible),
            key=lambda item: (item.current_rank or 10**9, item.symbol),
        )[:maximum]
        analyses = []
        for opportunity in opportunities:
            candidate = self.scanner_state.candidates.get(opportunity.symbol)
            if candidate is None:
                continue
            try:
                current = self.engine.evaluate(opportunity, candidate, timestamp)
                analyses.append(apply_lifecycle(self.state.analyses.get(opportunity.symbol), current))
            except Exception as exc:  # noqa: BLE001 - one symbol must not stop the batch
                structlog.get_logger().warning(
                    "STRATEGY_SYMBOL_ERROR",
                    symbol=opportunity.symbol,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
        results = [result for analysis in analyses for result in analysis.results.values()]
        stats = StrategyStatistics(
            evaluated_at=timestamp,
            symbols_evaluated=len(analyses),
            strategies_evaluated=len(results),
            status_counts=dict(Counter(result.status.value for result in results)),
            strategy_counts=dict(Counter(result.strategy.value for result in results)),
            duration_ms=(perf_counter() - started) * 1000,
        )
        await self.state.replace(analyses, stats)
        structlog.get_logger().info(
            "STRATEGY_BATCH_COMPLETED",
            symbols=stats.symbols_evaluated,
            strategies=stats.strategies_evaluated,
            milliseconds=stats.duration_ms,
        )
        if self.on_completed is not None:
            await self.on_completed(stats)
        return stats
