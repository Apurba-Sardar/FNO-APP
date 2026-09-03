from datetime import UTC, datetime
from types import MethodType, SimpleNamespace
from uuid import uuid4

import pytest

from app.execution.config import ExecutionStage, LiveExecutionConfig
from app.execution.error_policy import APIErrorCategory, classify_api_error
from app.execution.exceptions import LiveConfigurationError
from app.execution.models import LiveRuntimeState, ReconciliationReport
from app.execution.repository import InMemoryLiveRepository
from app.execution.runtime import LiveExecutionRuntime
from app.strategy.models import StrategyName, StrategyStatus


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


@pytest.mark.asyncio
async def test_periodic_reconciliation_preserves_armed_state_when_healthy():
    class HealthyReconciler:
        async def reconcile(self, _orders, _positions):
            return ReconciliationReport(healthy=True)

    repo = InMemoryLiveRepository()
    runtime = LiveExecutionRuntime(LiveExecutionConfig(), repo)
    runtime.reconciler = HealthyReconciler()
    runtime.state = LiveRuntimeState.ARMED

    await runtime.reconcile(actor="system")

    assert runtime.state == LiveRuntimeState.ARMED


@pytest.mark.asyncio
async def test_stage_five_submits_one_triggered_risk_approved_setup():
    now = datetime.now(UTC)
    strategy = StrategyName.TREND_PULLBACK
    analysis = SimpleNamespace(
        symbol="BTC_USDT",
        opportunity_score=90,
        results={strategy: SimpleNamespace(status=StrategyStatus.TRIGGERED, evaluation_timestamp=now)},
    )
    risk_analysis = SimpleNamespace(decisions={strategy: SimpleNamespace(allowed=True)})
    strategy_runtime = SimpleNamespace(state=SimpleNamespace(analyses={"BTC_USDT": analysis}))
    risk_runtime = SimpleNamespace(state=SimpleNamespace(analyses={"BTC_USDT": risk_analysis}))
    runtime = LiveExecutionRuntime(
        LiveExecutionConfig(
            trading_mode="live",
            enabled=True,
            confirmation="confirm",
            stage=ExecutionStage.AUTOMATIC,
            auto_execution=True,
        ),
        InMemoryLiveRepository(),
        strategy_runtime=strategy_runtime,
        risk_runtime=risk_runtime,
    )
    runtime.state = LiveRuntimeState.ARMED
    execution_id = uuid4()
    calls = []

    async def request_execution(self, setup_id):
        calls.append(("request", setup_id))
        return SimpleNamespace(execution_request_id=execution_id), "grant"

    async def confirm_execution(self, request_id, token, phrase, *, actor="operator"):
        calls.append(("confirm", request_id, token, phrase, actor))

    runtime.request_execution = MethodType(request_execution, runtime)
    runtime.confirm_execution = MethodType(confirm_execution, runtime)

    await runtime.process_risk_results()

    assert calls == [
        ("request", f"BTC_USDT:{strategy.value}:{now.isoformat()}"),
        ("confirm", execution_id, "grant", "EXECUTE REAL TRADE", "automatic_strategy"),
    ]


@pytest.mark.asyncio
async def test_stage_five_never_submits_while_runtime_is_not_armed():
    runtime = LiveExecutionRuntime(
        LiveExecutionConfig(
            trading_mode="live",
            enabled=True,
            confirmation="confirm",
            stage=ExecutionStage.AUTOMATIC,
            auto_execution=True,
        ),
        InMemoryLiveRepository(),
        strategy_runtime=SimpleNamespace(state=SimpleNamespace(analyses={})),
        risk_runtime=SimpleNamespace(state=SimpleNamespace(analyses={})),
    )
    runtime.state = LiveRuntimeState.RECONCILED

    async def unexpected_request(self, _setup_id):
        raise AssertionError("automatic execution was reached while unarmed")

    runtime.request_execution = MethodType(unexpected_request, runtime)
    await runtime.process_risk_results()


def test_api_errors_are_classified_for_safe_retry_policy():
    assert classify_api_error(429, "rate limited") == APIErrorCategory.RATE_LIMIT
    assert classify_api_error(400, "Insufficient funds") == APIErrorCategory.INSUFFICIENT_MARGIN
    assert classify_api_error(422, "Quantity should be greater") == APIErrorCategory.INVALID_QUANTITY
