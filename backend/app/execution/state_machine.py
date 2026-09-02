from datetime import UTC, datetime

from .models import ExecutionIntent, ExecutionState

ALLOWED_TRANSITIONS = {
    ExecutionState.EXECUTION_REQUESTED: {ExecutionState.VALIDATING, ExecutionState.REJECTED},
    ExecutionState.VALIDATING: {ExecutionState.RISK_RECHECK, ExecutionState.REJECTED},
    ExecutionState.RISK_RECHECK: {ExecutionState.SUBMITTING, ExecutionState.REJECTED},
    ExecutionState.SUBMITTING: {ExecutionState.ORDER_UNKNOWN, ExecutionState.ORDER_OPEN, ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.FAILED},
    ExecutionState.ORDER_UNKNOWN: {ExecutionState.RECONCILING, ExecutionState.CRITICAL},
    ExecutionState.RECONCILING: {ExecutionState.ORDER_OPEN, ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.CLOSED, ExecutionState.CRITICAL},
    ExecutionState.ORDER_OPEN: {ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.EXIT_REQUESTED, ExecutionState.FAILED},
    ExecutionState.PARTIALLY_FILLED: {ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.PROTECTION_PENDING, ExecutionState.EXIT_REQUESTED},
    ExecutionState.FILLED: {ExecutionState.PROTECTION_PENDING, ExecutionState.EXIT_REQUESTED},
    ExecutionState.PROTECTION_PENDING: {ExecutionState.PROTECTED, ExecutionState.EXIT_REQUESTED, ExecutionState.CRITICAL},
    ExecutionState.PROTECTED: {ExecutionState.EXIT_REQUESTED, ExecutionState.RECONCILING, ExecutionState.CLOSED, ExecutionState.CRITICAL},
    ExecutionState.EXIT_REQUESTED: {ExecutionState.EXITING, ExecutionState.CLOSED, ExecutionState.CRITICAL},
    ExecutionState.EXITING: {ExecutionState.CLOSED, ExecutionState.CRITICAL},
}


def transition(intent: ExecutionIntent, target: ExecutionState) -> ExecutionIntent:
    if target not in ALLOWED_TRANSITIONS.get(intent.state, set()):
        raise ValueError(f"invalid execution transition {intent.state} -> {target}")
    return intent.model_copy(update={"state": target, "updated_at": datetime.now(UTC)})
