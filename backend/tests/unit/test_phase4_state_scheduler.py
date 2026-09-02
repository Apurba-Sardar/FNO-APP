from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.scanner.config import ScannerConfig
from app.scanner.models import ScannerRunStatus
from app.scanner.scheduler import ScannerRuntime
from app.scanner.state import ScannerStateStore


class UnavailableRedis:
    async def setex(self, *_args):
        raise RedisError("fixture unavailable")


@pytest.mark.asyncio
async def test_redis_failure_does_not_break_in_memory_state():
    state = ScannerStateStore(UnavailableRedis(), 300, 900)
    await state.mark_status(ScannerRunStatus.RUNNING)
    assert state.status == ScannerRunStatus.RUNNING


@pytest.mark.asyncio
async def test_scheduler_can_start_and_stop_without_running_scanner():
    config = ScannerConfig(interval_seconds=60)
    state = ScannerStateStore(None, 60, 900)
    runtime = ScannerRuntime(AsyncMock(), state, config)
    await runtime.start_runtime()
    await runtime.start_scanning()
    assert state.scheduled
    assert runtime.scheduler.get_job(runtime.JOB_ID) is not None
    await runtime.stop_scanning()
    assert not state.scheduled
    await runtime.shutdown()
