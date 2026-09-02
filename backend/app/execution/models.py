from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.strategy.models import StrategyDirection, StrategyName


class ExecutionModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class LiveRuntimeState(StrEnum):
    DISABLED = "disabled"
    RECONCILING = "reconciling"
    RECONCILED = "reconciled"
    ARMED = "armed"
    READY = "ready"
    EXECUTING = "executing"
    BLOCKED = "blocked"
    CRITICAL = "critical"


class ExecutionState(StrEnum):
    EXECUTION_REQUESTED = "execution_requested"
    VALIDATING = "validating"
    RISK_RECHECK = "risk_recheck"
    SUBMITTING = "submitting"
    ORDER_UNKNOWN = "order_unknown"
    ORDER_OPEN = "order_open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PROTECTION_PENDING = "protection_pending"
    PROTECTED = "protected"
    EXIT_REQUESTED = "exit_requested"
    EXITING = "exiting"
    CLOSED = "closed"
    RECONCILING = "reconciling"
    REJECTED = "rejected"
    FAILED = "failed"
    CRITICAL = "critical"


class OrderState(StrEnum):
    INTENT_CREATED = "intent_created"
    VALIDATING = "validating"
    SUBMITTING = "submitting"
    UNKNOWN = "unknown"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"
    RECONCILED = "reconciled"


class ProtectionStatus(StrEnum):
    PENDING = "pending"
    PROTECTED = "protected"
    UNPROTECTED = "unprotected"
    UNKNOWN = "unknown"
    FAILED = "failed"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    CRITICAL = "critical"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class EmergencyStopState(StrEnum):
    ARMED = "armed"
    TRIGGERED = "triggered"


class ExecutionIntent(ExecutionModel):
    execution_request_id: UUID = Field(default_factory=uuid4)
    setup_id: str
    risk_decision_id: str
    symbol: str
    exchange_pair: str
    strategy: StrategyName
    direction: StrategyDirection
    quantity: float = Field(gt=0)
    expected_entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    leverage: float = Field(ge=1)
    notional: float = Field(gt=0)
    risk_amount: float = Field(ge=0)
    estimated_fees: float = Field(ge=0)
    estimated_slippage: float = Field(ge=0)
    setup_timestamp: datetime
    risk_timestamp: datetime
    strategy_version: str
    risk_version: str
    state: ExecutionState = ExecutionState.EXECUTION_REQUESTED
    rejection_reasons: list[str] = Field(default_factory=list)
    exchange_order_id: str | None = None
    exchange_position_id: str | None = None
    actual_quantity: float = Field(default=0, ge=0)
    actual_entry: float | None = Field(default=None, gt=0)
    actual_fees: float = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConfirmationGrant(ExecutionModel):
    execution_request_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None


class LiveOrder(ExecutionModel):
    order_id: UUID = Field(default_factory=uuid4)
    execution_request_id: UUID
    exchange_order_id: str | None = None
    pair: str
    side: str
    requested_quantity: float = Field(gt=0)
    filled_quantity: float = Field(default=0, ge=0)
    remaining_quantity: float = Field(default=0, ge=0)
    average_price: float | None = Field(default=None, ge=0)
    fees: float = Field(default=0, ge=0)
    status: OrderState = OrderState.INTENT_CREATED
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LivePosition(ExecutionModel):
    position_id: UUID = Field(default_factory=uuid4)
    execution_request_id: UUID | None = None
    exchange_position_id: str
    pair: str
    direction: StrategyDirection
    quantity: float
    average_price: float = Field(gt=0)
    mark_price: float | None = Field(default=None, gt=0)
    liquidation_price: float | None = Field(default=None, ge=0)
    leverage: float = Field(ge=1)
    margin_mode: str
    margin: float = Field(default=0, ge=0)
    stop: float | None = Field(default=None, gt=0)
    target: float | None = Field(default=None, gt=0)
    protection_status: ProtectionStatus = ProtectionStatus.UNKNOWN
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    fees: float = Field(default=0, ge=0)
    status: str = "open"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LiveAccount(ExecutionModel):
    equity: float | None = Field(default=None, ge=0)
    available_balance: float | None = Field(default=None, ge=0)
    locked_margin: float = Field(default=0, ge=0)
    cross_order_margin: float = Field(default=0, ge=0)
    cross_user_margin: float = Field(default=0, ge=0)
    daily_pnl: float = 0
    timestamp: datetime | None = None


class GateCheck(ExecutionModel):
    name: str
    passed: bool
    detail: str


class GateResult(ExecutionModel):
    passed: bool
    checks: list[GateCheck]

    @property
    def reasons(self) -> list[str]:
        return [check.detail for check in self.checks if not check.passed]


class ReconciliationReport(ExecutionModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    matched_positions: int = 0
    matched_orders: int = 0
    orphan_positions: list[str] = Field(default_factory=list)
    ghost_positions: list[str] = Field(default_factory=list)
    orphan_orders: list[str] = Field(default_factory=list)
    unknown_orders_resolved: int = 0
    protection_failures: list[str] = Field(default_factory=list)
    healthy: bool = False


class AuditEvent(ExecutionModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str
    event_type: str
    setup_id: str | None = None
    risk_decision_id: str | None = None
    execution_request_id: UUID | None = None
    symbol: str | None = None
    direction: str | None = None
    quantity: float | None = None
    expected_price: float | None = None
    actual_price: float | None = None
    order_id: str | None = None
    position_id: str | None = None
    fees: float | None = None
    result: str
    api_status: int | None = None
    rejection_reason: str | None = None
    strategy_version: str | None = None
    risk_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
