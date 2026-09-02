from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ScannerConfig(BaseModel):
    interval_seconds: int = Field(default=300, ge=30)
    max_concurrency: int = Field(default=5, ge=1, le=20)
    history_limit: int = Field(default=220, ge=200, le=1000)
    candidate_candle_limit: int = Field(default=220, ge=50, le=1000)
    orderbook_depth: Literal[10, 20, 50] = 20
    intended_notional: float = Field(default=1_000, gt=0)
    max_ticker_age_seconds: int = Field(default=120, ge=10)
    max_orderbook_age_seconds: int = Field(default=30, ge=5)
    min_volume_24h: float = Field(default=100_000, ge=0)
    max_spread_percent: float = Field(default=0.25, gt=0)
    max_slippage_percent: float = Field(default=0.35, gt=0)
    unknown_liquidity_eligible: bool = False
    excellent_spread_percent: float = Field(default=0.03, gt=0)
    good_spread_percent: float = Field(default=0.08, gt=0)
    excellent_slippage_percent: float = Field(default=0.05, gt=0)
    good_slippage_percent: float = Field(default=0.10, gt=0)
    excellent_depth_quote: float = Field(default=100_000, gt=0)
    good_depth_quote: float = Field(default=25_000, gt=0)
    acceptable_depth_quote: float = Field(default=2_000, gt=0)
    quiet_relative_volume: float = Field(default=0.75, ge=0)
    active_relative_volume: float = Field(default=1.5, gt=0)
    high_activity_relative_volume: float = Field(default=2.0, gt=0)
    extreme_relative_volume: float = Field(default=3.0, gt=0)
    minimum_atr_percent: float = Field(default=0.10, ge=0)
    high_atr_percent: float = Field(default=2.5, gt=0)
    extreme_atr_percent: float = Field(default=5.0, gt=0)
    filter_extreme_volatility: bool = True
    filter_dormant_activity: bool = True
    auto_start: bool = False
    control_token: str = ""
    state_ttl_seconds: int = Field(default=900, ge=60)

    @model_validator(mode="after")
    def ordered_thresholds(self) -> "ScannerConfig":
        if not self.excellent_spread_percent < self.good_spread_percent < self.max_spread_percent:
            raise ValueError("spread thresholds must be excellent < good < maximum")
        if not (
            self.excellent_slippage_percent < self.good_slippage_percent < self.max_slippage_percent
        ):
            raise ValueError("slippage thresholds must be excellent < good < maximum")
        if not self.minimum_atr_percent < self.high_atr_percent < self.extreme_atr_percent:
            raise ValueError("ATR thresholds must be minimum < high < extreme")
        return self
