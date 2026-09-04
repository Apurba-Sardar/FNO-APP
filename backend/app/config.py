from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.execution.config import LiveExecutionConfig
from app.indicators.models import IndicatorParameters
from app.paper_trading.config import PaperExecutionModel, PaperMarkPrice, PaperTradingConfig
from app.risk.config import RiskConfig
from app.scanner.config import ScannerConfig
from app.scoring.config import ScoreWeights, ScoringConfig
from app.strategy.config import StrategyConfig


class ScannerSettings(BaseModel):
    min_history_bars: int = 220
    min_quote_volume: float = 100_000
    max_spread_bps: float = 25
    max_slippage_bps: float = 35
    max_data_age_seconds: int = 120
    depth_levels: Literal[10, 20, 50] = 20
    depth_window_bps: float = 50
    slippage_test_notional: float = 1_000
    relative_volume_lookback: int = 20


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_nested_delimiter="__", extra="ignore")
    app_name: str = "CoinDCX Futures Scanner"
    environment: Literal["development", "test", "production"] = "development"
    coindcx_api_key: str = ""
    coindcx_api_secret: str = ""
    trading_mode: Literal["paper", "live"] = "live"
    database_url: str = "postgresql+asyncpg://fno:fno@localhost:5432/fno"
    redis_url: str = "redis://localhost:6379/0"
    coindcx_api_base_url: str = "https://api.coindcx.com"
    coindcx_public_base_url: str = "https://public.coindcx.com"
    coindcx_websocket_url: str = "wss://stream.coindcx.com"
    coindcx_requests_per_second: float = Field(default=15, gt=0, le=16)
    coindcx_max_retries: int = Field(default=3, ge=0, le=10)
    coindcx_websocket_enabled: bool = True
    coindcx_websocket_stale_seconds: int = Field(default=45, ge=10)
    market_cache_ttl_seconds: int = Field(default=300, ge=1)
    latest_market_data_ttl_seconds: int = Field(default=120, ge=1)
    request_timeout_seconds: float = Field(default=10, gt=0)
    candle_cache_ttl_seconds: int = Field(default=30, ge=1)
    analysis_history_limit: int = Field(default=220, ge=20, le=1000)
    analysis: IndicatorParameters = IndicatorParameters()
    market_scanner: ScannerConfig = ScannerConfig()
    scoring: ScoringConfig = ScoringConfig()
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    paper_initial_equity: float = Field(default=100_000, gt=0)
    paper_execution_model: PaperExecutionModel = PaperExecutionModel.SLIPPAGE_ADJUSTED
    paper_entry_slippage_bps: float = Field(default=5, ge=0)
    paper_exit_slippage_bps: float = Field(default=5, ge=0)
    paper_symbol_cooldown_minutes: int = Field(default=30, ge=0)
    paper_max_stale_seconds: int = Field(default=45, ge=1)
    paper_position_mark_price: PaperMarkPrice = PaperMarkPrice.EXIT_SIDE
    paper_reset_requires_confirmation: bool = True
    paper_funding_enabled: bool = False
    paper_auto_start: bool = False
    live_trading_enabled: bool = True
    live_trading_confirmation: str = "LIVE_CONFIRM_SAFE_2026"
    live_operator_token: str = "LIVE_OPERATOR_TOKEN_2026"
    live_emergency_token: str = "LIVE_EMERGENCY_TOKEN_2026"
    live_stage: int = Field(default=3, ge=0, le=5)
    live_max_orders_per_day: int = Field(default=50, ge=1)
    live_max_trades_per_day: int = Field(default=25, ge=1)
    live_max_notional_per_trade: float = Field(default=100, gt=0)
    live_max_daily_profit_target: float = Field(default=10.0, ge=0.0)
    live_max_daily_loss_percent: float = Field(default=0.25, gt=0)
    live_max_open_positions: int = Field(default=5, ge=1)
    live_max_total_exposure: float = Field(default=2500, gt=0)
    live_max_order_retries: int = Field(default=1, ge=0, le=3)
    live_order_timeout_seconds: float = Field(default=10, gt=0)
    live_max_entry_drift_percent: float = Field(default=0.15, ge=0)
    live_max_risk_decision_age_seconds: int = Field(default=30, ge=1)
    live_require_tpsl_confirmation: bool = True
    live_emergency_stop: bool = False
    live_allow_leverage_change: bool = False
    live_auto_execution: bool = False
    live_margin_mode: Literal["isolated", "crossed"] = "isolated"
    live_confirmation_ttl_seconds: int = Field(default=30, ge=5, le=120)
    live_reconciliation_interval_seconds: int = Field(default=15, ge=5)
    live_max_consecutive_api_failures: int = Field(default=3, ge=1)
    scanner: ScannerSettings = ScannerSettings()
    score_weights: ScoreWeights = ScoreWeights()

    @property
    def paper(self) -> PaperTradingConfig:
        return PaperTradingConfig(
            initial_equity=self.paper_initial_equity,
            execution_model=self.paper_execution_model,
            entry_slippage_bps=self.paper_entry_slippage_bps,
            exit_slippage_bps=self.paper_exit_slippage_bps,
            symbol_cooldown_minutes=self.paper_symbol_cooldown_minutes,
            max_stale_seconds=self.paper_max_stale_seconds,
            position_mark_price=self.paper_position_mark_price,
            reset_requires_confirmation=self.paper_reset_requires_confirmation,
            funding_enabled=self.paper_funding_enabled,
            auto_start=self.paper_auto_start,
        )

    @property
    def live(self) -> LiveExecutionConfig:
        return LiveExecutionConfig(
            trading_mode=self.trading_mode,
            enabled=self.live_trading_enabled,
            confirmation=self.live_trading_confirmation,
            operator_token=self.live_operator_token,
            emergency_token=self.live_emergency_token,
            stage=self.live_stage,
            max_orders_per_day=self.live_max_orders_per_day,
            max_trades_per_day=self.live_max_trades_per_day,
            max_notional_per_trade=self.live_max_notional_per_trade,
            max_daily_profit_target=self.live_max_daily_profit_target,
            max_daily_loss_percent=self.live_max_daily_loss_percent,
            max_open_positions=self.live_max_open_positions,
            max_total_exposure=self.live_max_total_exposure,
            max_order_retries=self.live_max_order_retries,
            order_timeout_seconds=self.live_order_timeout_seconds,
            max_entry_drift_percent=self.live_max_entry_drift_percent,
            max_risk_decision_age_seconds=self.live_max_risk_decision_age_seconds,
            require_tpsl_confirmation=self.live_require_tpsl_confirmation,
            emergency_stop=self.live_emergency_stop,
            allow_leverage_change=self.live_allow_leverage_change,
            auto_execution=self.live_auto_execution,
            margin_mode=self.live_margin_mode,
            confirmation_ttl_seconds=self.live_confirmation_ttl_seconds,
            reconciliation_interval_seconds=self.live_reconciliation_interval_seconds,
            max_consecutive_api_failures=self.live_max_consecutive_api_failures,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
