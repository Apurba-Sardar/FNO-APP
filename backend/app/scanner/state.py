from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .models import (
    ScannerCandidate,
    ScannerRunStatus,
    ScannerStatistics,
    ScannerStatusSnapshot,
    SymbolScannerState,
)


class ScannerStateStore:
    """Latest-state store with Redis persistence and an in-memory fallback."""

    def __init__(self, redis: Redis | None, interval_seconds: int, ttl_seconds: int) -> None:
        self.redis = redis
        self.interval_seconds = interval_seconds
        self.ttl_seconds = ttl_seconds
        self.candidates: dict[str, ScannerCandidate] = {}
        self.symbols: dict[str, SymbolScannerState] = {}
        self.stats: ScannerStatistics | None = None
        self.status = ScannerRunStatus.STOPPED
        self.scheduled = False
        self.last_scan_at: datetime | None = None
        self.last_error: str | None = None

    async def replace(
        self,
        candidates: list[ScannerCandidate],
        symbol_states: dict[str, SymbolScannerState],
        stats: ScannerStatistics,
    ) -> None:
        self.candidates = {candidate.symbol: candidate for candidate in candidates}
        self.symbols = symbol_states
        self.stats = stats
        self.last_scan_at = stats.scan_completed_at
        await self._persist()

    def snapshot(self) -> ScannerStatusSnapshot:
        return ScannerStatusSnapshot(
            status=self.status,
            scheduled=self.scheduled,
            interval_seconds=self.interval_seconds,
            last_scan_at=self.last_scan_at,
            last_error=self.last_error,
            candidate_count=len(self.candidates),
            stats=self.stats,
        )

    def failure_count(self, symbol: str) -> int:
        previous = self.symbols.get(symbol)
        return previous.failure_count if previous else 0

    async def load(self) -> None:
        """Restore the latest bounded snapshot when Redis still has it."""
        if self.redis is None:
            return
        try:
            candidates = await self.redis.hgetall("scanner:candidates")
            symbols = await self.redis.hgetall("scanner:symbol_states")
            stats = await self.redis.get("scanner:stats")
            self.candidates = {
                key.decode()
                if isinstance(key, bytes)
                else key: ScannerCandidate.model_validate_json(value)
                for key, value in candidates.items()
            }
            self.symbols = {
                key.decode()
                if isinstance(key, bytes)
                else key: SymbolScannerState.model_validate_json(value)
                for key, value in symbols.items()
            }
            if stats:
                self.stats = ScannerStatistics.model_validate_json(stats)
                self.last_scan_at = self.stats.scan_completed_at
        except (RedisError, ValueError) as exc:
            structlog.get_logger().warning("SCANNER_STATE_RESTORE_FAILED", error=str(exc))

    async def _persist(self) -> None:
        if self.redis is None:
            return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.delete("scanner:candidates", "scanner:symbol_states")
                if self.candidates:
                    pipe.hset(
                        "scanner:candidates",
                        mapping={
                            symbol: candidate.model_dump_json()
                            for symbol, candidate in self.candidates.items()
                        },
                    )
                    pipe.expire("scanner:candidates", self.ttl_seconds)
                if self.symbols:
                    pipe.hset(
                        "scanner:symbol_states",
                        mapping={
                            symbol: state.model_dump_json()
                            for symbol, state in self.symbols.items()
                        },
                    )
                    pipe.expire("scanner:symbol_states", self.ttl_seconds)
                pipe.setex("scanner:stats", self.ttl_seconds, self.stats.model_dump_json())
                await pipe.execute()
        except RedisError as exc:
            structlog.get_logger().warning("SCANNER_STATE_REDIS_UNAVAILABLE", error=str(exc))

    async def mark_status(self, status: ScannerRunStatus, *, error: str | None = None) -> None:
        self.status = status
        self.last_error = error
        if status == ScannerRunStatus.RUNNING:
            self.last_error = None
        if self.redis is None:
            return
        try:
            await self.redis.setex(
                "scanner:status", self.ttl_seconds, self.snapshot().model_dump_json()
            )
        except RedisError as exc:
            structlog.get_logger().warning("SCANNER_STATE_REDIS_UNAVAILABLE", error=str(exc))

    @staticmethod
    def new_symbol_state(
        candidate: ScannerCandidate,
        previous: SymbolScannerState | None,
    ) -> SymbolScannerState:
        failed = candidate.status.value in {"data_error", "stale", "insufficient_data"}
        return SymbolScannerState(
            symbol=candidate.symbol,
            last_scan_time=candidate.scan_timestamp,
            candidate=candidate,
            last_successful_scan=(
                previous.last_successful_scan if failed and previous else candidate.scan_timestamp
            ),
            last_failure="; ".join(candidate.warnings) if failed else None,
            failure_count=(previous.failure_count if previous else 0) + 1 if failed else 0,
            data_fresh=candidate.market.fresh,
            processing_duration_ms=candidate.processing_duration_ms,
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
