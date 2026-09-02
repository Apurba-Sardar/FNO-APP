from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from redis.exceptions import RedisError

from .config import BacktestConfig
from .data_provider import DatabaseHistoricalDataProvider
from .engine import BacktestEngine
from .models import BacktestResult, BacktestStatus


class BacktestStateStore:
    def __init__(self, redis=None, key: str = "backtest:results") -> None:
        self.redis = redis
        self.key = key
        self.results: dict[UUID, BacktestResult] = {}

    async def load(self) -> None:
        if self.redis is None:
            return
        try:
            rows = await self.redis.hgetall(self.key)
            self.results = {
                UUID(key.decode() if isinstance(key, bytes) else key): BacktestResult.model_validate_json(value)
                for key, value in rows.items()
            }
        except (RedisError, ValueError) as exc:
            structlog.get_logger().error("BACKTEST_STATE_RESTORE_FAILED", error=str(exc))

    async def save(self, result: BacktestResult) -> None:
        self.results[result.backtest_id] = result
        if self.redis is None:
            return
        try:
            await self.redis.hset(self.key, str(result.backtest_id), result.model_dump_json())
        except RedisError as exc:
            structlog.get_logger().error("BACKTEST_STATE_PERSIST_FAILED", error=str(exc))


class BacktestRuntime:
    def __init__(self, session_factory, store: BacktestStateStore) -> None:
        self.session_factory = session_factory
        self.store = store

    async def create(self, config: BacktestConfig) -> BacktestResult:
        result = BacktestResult(
            backtest_id=uuid4(),
            status=BacktestStatus.CREATED,
            configuration=config,
            created_at=datetime.now(UTC),
        )
        await self.store.save(result)
        return result

    async def run(self, backtest_id: UUID) -> BacktestResult:
        existing = self.store.results.get(backtest_id)
        if existing is None:
            raise KeyError(str(backtest_id))
        async with self.session_factory() as session:
            result = await BacktestEngine(DatabaseHistoricalDataProvider(session)).run(
                existing.configuration, backtest_id
            )
        await self.store.save(result)
        return result
