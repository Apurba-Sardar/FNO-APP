from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class MissingDataPolicy(StrEnum):
    REJECT = "reject"
    ALLOW_WITH_WARNING = "allow_with_warning"


class RiskConfig(BaseModel):
    risk_per_trade_percent: float = Field(default=0.5, gt=0, le=100)
    max_daily_loss_percent: float = Field(default=2.0, gt=0, le=100)
    max_consecutive_losses: int = Field(default=3, ge=1)
    max_open_positions: int = Field(default=1, ge=0)
    max_total_exposure_percent: float = Field(default=100, gt=0)
    minimum_risk_reward: float = Field(default=1.5, gt=0)
    max_leverage: float = Field(default=5, ge=1)
    max_position_notional: float = Field(default=100_000, gt=0)
    max_spread_percent: float = Field(default=0.25, gt=0)
    max_estimated_slippage_percent: float = Field(default=0.35, gt=0)
    slippage_safety_buffer_percent: float = Field(default=0.05, ge=0)
    slippage_round_trip_multiplier: float = Field(default=2, ge=1)
    missing_slippage_policy: MissingDataPolicy = MissingDataPolicy.REJECT
    missing_spread_policy: MissingDataPolicy = MissingDataPolicy.REJECT
    min_stop_distance_atr: float = Field(default=0.4, gt=0)
    max_stop_distance_atr: float = Field(default=4, gt=0)
    max_trade_duration_minutes: int = Field(default=240, ge=1)
    max_setup_age_minutes: int = Field(default=60, ge=1)
    max_market_data_age_seconds: int = Field(default=300, ge=1)
    max_account_data_age_seconds: int = Field(default=300, ge=1)
    max_entry_drift_percent: float = Field(default=0.25, gt=0)
    maker_fee_percent: float = Field(default=0.02, ge=0)
    taker_fee_percent: float = Field(default=0.05, ge=0)
    fee_mode: str = "taker"
    margin_safety_buffer_percent: float = Field(default=20, ge=0, lt=100)
    one_direction_per_symbol: bool = True
    include_unrealized_loss_in_daily_limit: bool = True
    consecutive_loss_cooldown_minutes: int = Field(default=1440, ge=0)
    utc_day_boundary_hour: int = Field(default=0, ge=0, le=23)
    control_token: str = ""
    state_key: str = "risk:state"
    decisions_key: str = "risk:decisions"

    @model_validator(mode="after")
    def validate_thresholds(self) -> "RiskConfig":
        if self.min_stop_distance_atr >= self.max_stop_distance_atr:
            raise ValueError("minimum stop ATR distance must be below maximum")
        if self.fee_mode not in {"maker", "taker"}:
            raise ValueError("fee_mode must be maker or taker")
        return self
