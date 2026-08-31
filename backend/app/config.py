from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoreWeights(BaseModel):
    weekly_trend: float = 10
    daily_trend: float = 15
    four_hour_trend: float = 15
    one_hour_momentum: float = 10
    fifteen_minute_setup: float = 15
    volume_expansion: float = 10
    liquidity_order_book: float = 10
    volatility_atr: float = 5
    support_resistance: float = 5
    risk_reward: float = 5

    @model_validator(mode="after")
    def total_is_100(self) -> "ScoreWeights":
        if abs(sum(self.model_dump().values()) - 100) > 1e-9:
            raise ValueError("opportunity score weights must total 100")
        return self


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
    model_config = SettingsConfigDict(env_file="../.env", env_nested_delimiter="__", extra="ignore")
    app_name: str = "CoinDCX Futures Scanner"
    environment: Literal["development", "test", "production"] = "development"
    coindcx_api_key: str = ""
    coindcx_api_secret: str = ""
    trading_mode: Literal["paper", "live"] = "paper"
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
    scanner: ScannerSettings = ScannerSettings()
    score_weights: ScoreWeights = ScoreWeights()


@lru_cache
def get_settings() -> Settings:
    return Settings()
