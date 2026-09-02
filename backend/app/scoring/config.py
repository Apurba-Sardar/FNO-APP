from pydantic import BaseModel, Field, model_validator


class ScoreWeights(BaseModel):
    weekly_trend: float = Field(default=10, ge=0)
    daily_trend: float = Field(default=15, ge=0)
    four_hour_trend: float = Field(default=15, ge=0)
    one_hour_momentum: float = Field(default=10, ge=0)
    fifteen_minute_setup: float = Field(default=15, ge=0)
    volume_expansion: float = Field(default=10, ge=0)
    liquidity_order_book: float = Field(default=10, ge=0)
    volatility_atr: float = Field(default=5, ge=0)
    support_resistance: float = Field(default=5, ge=0)
    risk_reward: float = Field(default=5, ge=0)

    @model_validator(mode="after")
    def total_is_100(self) -> "ScoreWeights":
        if abs(sum(self.model_dump().values()) - 100) > 1e-9:
            raise ValueError("opportunity score weights must total 100")
        return self


class ScoringConfig(BaseModel):
    weights: ScoreWeights = ScoreWeights()
    tier_a_plus: float = Field(default=90, ge=0, le=100)
    tier_a: float = Field(default=80, ge=0, le=100)
    tier_b: float = Field(default=70, ge=0, le=100)
    tier_c: float = Field(default=60, ge=0, le=100)
    direction_difference_threshold: float = Field(default=5, ge=0, le=100)
    maximum_spread_percent: float = Field(default=0.25, gt=0)
    minimum_liquidity: str = "acceptable"
    exclude_extreme_volatility: bool = True
    hypothetical_atr_stop_multiple: float = Field(default=1.5, gt=0)
    rr_full_score: float = Field(default=2.5, gt=0)
    nearby_level_atr_multiple: float = Field(default=0.75, gt=0)
    maximum_displayed_opportunities: int = Field(default=10, ge=1, le=100)
    state_ttl_seconds: int = Field(default=900, ge=60)
    control_token: str = ""

    @model_validator(mode="after")
    def ordered_tiers(self) -> "ScoringConfig":
        if not 0 <= self.tier_c < self.tier_b < self.tier_a < self.tier_a_plus <= 100:
            raise ValueError("score tiers must be ordered C < B < A < A+")
        if self.minimum_liquidity not in {"excellent", "good", "acceptable"}:
            raise ValueError("minimum liquidity must be excellent, good, or acceptable")
        return self
