from collections import Counter
from time import perf_counter

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import ScoringConfig
from .engine import OpportunityScoringEngine
from .exceptions import NoScannerCandidates
from .models import Opportunity, OpportunityStatistics
from .ranking import OpportunityRankingService


class OpportunityState:
    def __init__(self, redis: Redis | None, config: ScoringConfig) -> None:
        self.redis = redis
        self.config = config
        self.opportunities: dict[str, Opportunity] = {}
        self.stats: OpportunityStatistics | None = None

    async def load(self) -> None:
        """Restore the latest TTL-bounded ranking snapshot after a process restart."""
        if self.redis is None:
            return
        try:
            rows = await self.redis.hgetall("opportunities:current")
            stats = await self.redis.get("opportunities:stats")
            self.opportunities = {
                key.decode() if isinstance(key, bytes) else key: Opportunity.model_validate_json(
                    value
                )
                for key, value in rows.items()
            }
            if stats:
                self.stats = OpportunityStatistics.model_validate_json(stats)
        except (RedisError, ValueError) as exc:
            structlog.get_logger().warning("OPPORTUNITY_STATE_RESTORE_FAILED", error=str(exc))

    async def replace(self, opportunities: list[Opportunity], stats: OpportunityStatistics) -> None:
        self.opportunities = {item.symbol: item for item in opportunities}
        self.stats = stats
        if self.redis is None:
            return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.delete("opportunities:current")
                if opportunities:
                    pipe.hset(
                        "opportunities:current",
                        mapping={item.symbol: item.model_dump_json() for item in opportunities},
                    )
                    pipe.expire("opportunities:current", self.config.state_ttl_seconds)
                pipe.setex(
                    "opportunities:stats",
                    self.config.state_ttl_seconds,
                    stats.model_dump_json(),
                )
                await pipe.execute()
        except RedisError as exc:
            structlog.get_logger().warning("OPPORTUNITY_STATE_REDIS_UNAVAILABLE", error=str(exc))


class OpportunityRuntime:
    def __init__(
        self,
        scanner_state,
        state: OpportunityState,
        engine: OpportunityScoringEngine,
        ranking: OpportunityRankingService | None = None,
        on_completed=None,
    ) -> None:
        self.scanner_state = scanner_state
        self.state = state
        self.engine = engine
        self.ranking = ranking or OpportunityRankingService()
        self.on_completed = on_completed

    async def recalculate(self, *_args) -> OpportunityStatistics:
        candidates = list(self.scanner_state.candidates.values())
        if not candidates:
            raise NoScannerCandidates("run the market scanner before recalculating opportunities")
        started = perf_counter()
        scored = [self.engine.score_candidate(candidate) for candidate in candidates]
        scoring_elapsed = perf_counter() - started
        ranked, ranking_time_ms = self.ranking.rank(scored, self.state.opportunities)
        exclusions = Counter(
            reason for item in ranked if not item.eligible for reason in item.hard_gate_reasons
        )
        stats = OpportunityStatistics(
            calculated_at=max(item.calculated_at for item in ranked),
            markets_analyzed=len(ranked),
            eligible_opportunities=sum(item.eligible for item in ranked),
            hard_gate_exclusions=sum(not item.eligible for item in ranked),
            calculation_time_ms=scoring_elapsed * 1000,
            ranking_time_ms=ranking_time_ms,
            average_scoring_time_ms=scoring_elapsed / len(ranked) * 1000,
            tier_counts=dict(Counter(item.tier.value for item in ranked if item.eligible)),
            direction_counts=dict(
                Counter(item.dominant_direction.value for item in ranked if item.eligible)
            ),
            exclusion_counts=dict(exclusions),
        )
        await self.state.replace(ranked, stats)
        structlog.get_logger().info(
            "OPPORTUNITY_CALCULATION_COMPLETED",
            analyzed=stats.markets_analyzed,
            eligible=stats.eligible_opportunities,
            milliseconds=stats.calculation_time_ms,
        )
        if self.on_completed is not None:
            await self.on_completed(stats)
        return stats
