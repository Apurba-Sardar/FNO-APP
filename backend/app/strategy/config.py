from pydantic import BaseModel, Field, model_validator


class SetupQualityWeights(BaseModel):
    trend_alignment: float = 10
    structure_quality: float = 10
    entry_location: float = 10
    trigger_quality: float = 10
    volume_confirmation: float = 10
    momentum_confirmation: float = 10
    liquidity: float = 10
    volatility: float = 10
    target_room: float = 10
    risk_reward: float = 10

    @model_validator(mode="after")
    def total_is_100(self) -> "SetupQualityWeights":
        if abs(sum(self.model_dump().values()) - 100) > 1e-9:
            raise ValueError("strategy quality weights must total 100")
        return self


class StrategyConfig(BaseModel):
    enabled: bool = True
    minimum_opportunity_score: float = Field(default=50, ge=0, le=100)
    minimum_setup_quality: float = Field(default=60, ge=0, le=100)
    minimum_risk_reward: float = Field(default=1.5, gt=0)
    preferred_risk_reward: float = Field(default=2.0, gt=0)
    maximum_spread_percent: float = Field(default=0.25, gt=0)
    maximum_slippage_percent: float = Field(default=0.35, gt=0)
    pullback_zone_atr: float = Field(default=0.35, gt=0)
    trigger_lookback: int = Field(default=5, ge=2, le=20)
    trigger_relative_volume: float = Field(default=1.2, ge=0)
    breakout_relative_volume: float = Field(default=1.5, ge=0)
    minimum_body_range_ratio: float = Field(default=0.5, ge=0, le=1)
    maximum_breakout_wick_ratio: float = Field(default=0.5, ge=0, le=1)
    minimum_breakout_distance_atr: float = Field(default=0.05, ge=0)
    maximum_breakout_distance_atr: float = Field(default=1.5, gt=0)
    consolidation_lookback: int = Field(default=20, ge=8, le=100)
    minimum_consolidation_candles: int = Field(default=8, ge=5, le=50)
    maximum_consolidation_width_atr: float = Field(default=6.0, gt=0)
    stop_atr_buffer: float = Field(default=0.35, gt=0)
    minimum_stop_distance_atr: float = Field(default=0.4, gt=0)
    maximum_stop_distance_atr: float = Field(default=4.0, gt=0)
    setup_expiry_minutes: int = Field(default=60, ge=5, le=1440)
    maximum_data_age_minutes: int = Field(default=30, ge=5, le=1440)
    maximum_evaluated_symbols: int = Field(default=25, ge=1, le=500)
    chart_candle_limit: int = Field(default=120, ge=20, le=500)
    retest_required: bool = False
    require_daily_alignment: bool = True
    require_four_hour_alignment: bool = True
    allow_weekly_neutral: bool = True
    disabled_regimes: set[str] = {"extreme"}
    excellent_quality_threshold: float = Field(default=90, ge=0, le=100)
    good_quality_threshold: float = Field(default=80, ge=0, le=100)
    acceptable_quality_threshold: float = Field(default=70, ge=0, le=100)
    weak_quality_threshold: float = Field(default=60, ge=0, le=100)
    control_token: str = ""
    state_ttl_seconds: int = Field(default=900, ge=60)
    quality_weights: SetupQualityWeights = SetupQualityWeights()

    @model_validator(mode="after")
    def valid_ranges(self) -> "StrategyConfig":
        if self.preferred_risk_reward < self.minimum_risk_reward:
            raise ValueError("preferred risk/reward must be at least the minimum")
        if self.minimum_stop_distance_atr >= self.maximum_stop_distance_atr:
            raise ValueError("minimum stop distance must be below maximum")
        if not (
            self.excellent_quality_threshold
            > self.good_quality_threshold
            > self.acceptable_quality_threshold
            > self.weak_quality_threshold
        ):
            raise ValueError("quality thresholds must be excellent > good > acceptable > weak")
        return self
