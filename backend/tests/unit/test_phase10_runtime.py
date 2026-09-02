import pytest

from app.execution.config import LiveExecutionConfig
from app.execution.error_policy import APIErrorCategory, classify_api_error
from app.execution.exceptions import LiveConfigurationError
from app.execution.models import LiveRuntimeState
from app.execution.repository import InMemoryLiveRepository
from app.execution.runtime import LiveExecutionRuntime


@pytest.mark.asyncio
async def test_restart_never_restores_armed_or_ready_state():
    repo = InMemoryLiveRepository()
    repo.runtime = {"runtime_state": "ready", "emergency_stop": "armed"}
    runtime = LiveExecutionRuntime(LiveExecutionConfig(), repo)
    await runtime.load()
    assert runtime.state == LiveRuntimeState.DISABLED


def test_live_startup_validation_fails_when_any_required_gate_is_missing():
    runtime = LiveExecutionRuntime(
        LiveExecutionConfig(trading_mode="live", enabled=False, confirmation="", stage=1),
        InMemoryLiveRepository(),
    )
    with pytest.raises(LiveConfigurationError) as exc:
        runtime.validate_startup()
    assert "LIVE_TRADING_ENABLED" in str(exc.value)
    assert "credentials" in str(exc.value)


@pytest.mark.asyncio
async def test_emergency_stop_is_persisted_and_blocks_runtime():
    repo = InMemoryLiveRepository()
    runtime = LiveExecutionRuntime(LiveExecutionConfig(), repo)
    await runtime.emergency()
    assert runtime.state == LiveRuntimeState.BLOCKED
    assert repo.runtime["emergency_stop"] == "triggered"


def test_api_errors_are_classified_for_safe_retry_policy():
    assert classify_api_error(429, "rate limited") == APIErrorCategory.RATE_LIMIT
    assert classify_api_error(400, "Insufficient funds") == APIErrorCategory.INSUFFICIENT_MARGIN
    assert classify_api_error(422, "Quantity should be greater") == APIErrorCategory.INVALID_QUANTITY
