from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.market import Timeframe
from app.market_data.models import Market
from app.risk.config import RiskConfig
from app.scoring.config import ScoringConfig
from app.strategy.config import StrategyConfig
from app.strategy.models import StrategyName


class MissingCandlePolicy(StrEnum):
    SKIP_PERIOD = "skip_period"
    ABORT_SYMBOL = "abort_symbol"


class IntrabarPolicy(StrEnum):
    ASSUME_STOP_FIRST = "assume_stop_first"
    ASSUME_TARGET_FIRST = "assume_target_first"


class ExecutionModel(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    BREAKOUT_TRIGGER = "breakout_trigger"


class SlippageModelKind(StrEnum):
    FIXED_BPS = "fixed_bps"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    ORDERBOOK_ESTIMATE = "orderbook_estimate"


class EndPositionPolicy(StrEnum):
    CLOSE_AT_LAST_AVAILABLE_PRICE = "close_at_last_available_price"


class FeeModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    maker_fee_percent: float = Field(default=0.02, ge=0)
    taker_fee_percent: float = Field(default=0.05, ge=0)
    use_taker: bool = True


class SlippageModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: SlippageModelKind = SlippageModelKind.FIXED_BPS
    entry_slippage_bps: float = Field(default=5, ge=0)
    exit_slippage_bps: float = Field(default=5, ge=0)
    volatility_multiplier: float = Field(default=1, ge=0)


class BacktestConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbols: tuple[str, ...]
    start_timestamp: datetime
    end_timestamp: datetime
    initial_equity: float = Field(default=100_000, gt=0)
    candle_timeframe: Timeframe = Timeframe.MINUTE_5
    evaluation_timeframe: Timeframe = Timeframe.MINUTE_15
    warmup_candles: int = Field(default=220, ge=50, le=2000)
    missing_candle_policy: MissingCandlePolicy = MissingCandlePolicy.SKIP_PERIOD
    intrabar_policy: IntrabarPolicy = IntrabarPolicy.ASSUME_STOP_FIRST
    execution_model: ExecutionModel = ExecutionModel.MARKET
    end_position_policy: EndPositionPolicy = EndPositionPolicy.CLOSE_AT_LAST_AVAILABLE_PRICE
    fee_model: FeeModelConfig = FeeModelConfig()
    slippage_model: SlippageModelConfig = SlippageModelConfig()
    funding_included: bool = False
    max_trade_duration_minutes: int = Field(default=240, ge=1)
    historical_spread_percent: float = Field(default=0.05, ge=0)
    entry_delay_candles: int = Field(default=1, ge=1, le=100)
    strategies: tuple[StrategyName, ...] = (
        StrategyName.TREND_PULLBACK,
        StrategyName.BREAKOUT,
    )
    minimum_opportunity_score: float = Field(default=50, ge=0, le=100)
    minimum_setup_score: float = Field(default=60, ge=0, le=100)
    strategy_version: str = "phase6-v1"
    scoring_version: str = "phase5-v1"
    risk_version: str = "phase7-v1"
    data_version: str = "postgres-normalized-candles-v1"
    execution_model_version: str = "phase8-v1"
    random_seed: int = 42
    scoring: ScoringConfig = ScoringConfig()
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    instrument_overrides: dict[str, Market] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_window(self) -> "BacktestConfig":
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        if self.start_timestamp >= self.end_timestamp:
            raise ValueError("start_timestamp must be before end_timestamp")
        if self.candle_timeframe != Timeframe.MINUTE_5:
            raise ValueError("Phase 8 execution currently requires normalized 5m candles")
        return self
