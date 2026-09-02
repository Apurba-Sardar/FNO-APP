from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PaperExecutionModel(StrEnum):
    MID_PRICE = "mid_price"
    LAST_PRICE = "last_price"
    ASK_FOR_LONG = "ask_for_long"
    BID_FOR_SHORT = "bid_for_short"
    SLIPPAGE_ADJUSTED = "slippage_adjusted"


class PaperMarkPrice(StrEnum):
    EXIT_SIDE = "exit_side"
    MID_PRICE = "mid_price"
    LAST_PRICE = "last_price"


class PaperTradingConfig(BaseModel):
    """Central Phase 9 configuration. Bid/ask plus adverse slippage is the default."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    initial_equity: float = Field(default=100_000, gt=0)
    execution_model: PaperExecutionModel = PaperExecutionModel.SLIPPAGE_ADJUSTED
    entry_slippage_bps: float = Field(default=5, ge=0)
    exit_slippage_bps: float = Field(default=5, ge=0)
    symbol_cooldown_minutes: int = Field(default=30, ge=0)
    max_stale_seconds: int = Field(default=45, ge=1)
    position_mark_price: PaperMarkPrice = PaperMarkPrice.EXIT_SIDE
    reset_requires_confirmation: bool = True
    funding_enabled: bool = False
    monitor_interval_seconds: float = Field(default=1, gt=0, le=60)
    minimum_health_sample: int = Field(default=30, ge=1)
    auto_start: bool = False
    strategy_version: str = "phase6-v1"
    risk_version: str = "phase7-v1"
