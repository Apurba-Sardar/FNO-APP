from enum import IntEnum, StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionStage(IntEnum):
    PAPER_ONLY = 0
    READ_ONLY = 1
    VALIDATION_ONLY = 2
    MANUAL_TINY = 3
    MANUAL_CONSERVATIVE = 4
    AUTOMATIC = 5


class MarginMode(StrEnum):
    ISOLATED = "isolated"
    CROSSED = "crossed"


class ProtectionFailurePolicy(StrEnum):
    EMERGENCY_EXIT = "emergency_exit"


class LiveExecutionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    trading_mode: Literal["paper", "live"] = "paper"
    enabled: bool = False
    confirmation: str = Field(default="", repr=False)
    operator_token: str = Field(default="", repr=False)
    emergency_token: str = Field(default="", repr=False)
    stage: ExecutionStage = ExecutionStage.PAPER_ONLY
    max_orders_per_day: int = Field(default=3, ge=1)
    max_trades_per_day: int = Field(default=1, ge=1)
    max_notional_per_trade: float = Field(default=25, gt=0)
    max_daily_profit_target: float = Field(default=10.0, ge=0.0)
    max_daily_loss_percent: float = Field(default=0.25, gt=0)
    max_open_positions: int = Field(default=10, ge=1)
    max_total_exposure: float = Field(default=2500, gt=0)
    max_order_retries: int = Field(default=1, ge=0, le=3)
    order_timeout_seconds: float = Field(default=10, gt=0)
    max_entry_drift_percent: float = Field(default=0.15, ge=0)
    max_risk_decision_age_seconds: int = Field(default=30, ge=1)
    require_tpsl_confirmation: bool = True
    emergency_stop: bool = False
    allow_leverage_change: bool = False
    auto_execution: bool = False
    margin_mode: MarginMode = MarginMode.ISOLATED
    confirmation_ttl_seconds: int = Field(default=30, ge=5, le=120)
    reconciliation_interval_seconds: int = Field(default=15, ge=5)
    max_consecutive_api_failures: int = Field(default=3, ge=1)
    protection_failure_policy: ProtectionFailurePolicy = ProtectionFailurePolicy.EMERGENCY_EXIT

    @model_validator(mode="after")
    def safe_stage(self):
        if self.stage == ExecutionStage.AUTOMATIC and not self.auto_execution:
            raise ValueError("stage 5 requires LIVE_AUTO_EXECUTION=true")
        if self.auto_execution and self.stage != ExecutionStage.AUTOMATIC:
            raise ValueError("auto execution is permitted only in stage 5")
        return self

    @property
    def submission_configured(self) -> bool:
        return (
            self.trading_mode == "live"
            and self.enabled
            and bool(self.confirmation)
            and self.stage >= ExecutionStage.MANUAL_TINY
        )

    def public_dict(self) -> dict:
        return self.model_dump(exclude={"confirmation", "operator_token", "emergency_token"}) | {
            "confirmation_configured": bool(self.confirmation),
            "operator_auth_configured": bool(self.operator_token),
            "emergency_auth_configured": bool(self.emergency_token),
            "submission_configured": self.submission_configured,
        }
