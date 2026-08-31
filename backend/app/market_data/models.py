from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.market import Timeframe


class MarketType(StrEnum):
    FUTURES = "futures"


class Market(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    market_type: MarketType
    status: str
    contract_kind: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    min_quantity: float | None = None
    min_notional: float | None = None
    tick_size: float | None = None
    step_size: float | None = None


class NormalizedCandle(BaseModel):
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def valid_ohlc(self) -> "NormalizedCandle":
        if self.high < self.low:
            raise ValueError("high is lower than low")
        if self.high < max(self.open, self.close):
            raise ValueError("high is below open or close")
        if self.low > min(self.open, self.close):
            raise ValueError("low is above open or close")
        return self


class CandleValidationIssue(BaseModel):
    index: int | None = None
    timestamp: str | None = None
    reason: str


class CandleResult(BaseModel):
    symbol: str
    timeframe: Timeframe
    candles: list[NormalizedCandle]
    validation_issues: list[CandleValidationIssue] = Field(default_factory=list)
    stale: bool = False
    cache_hit: bool = False


class Ticker(BaseModel):
    symbol: str
    timestamp: datetime
    last_price: float | None = None
    mark_price: float | None = None
    high_24h: float | None = None
    low_24h: float | None = None
    volume_24h: float | None = None
    price_change_percent: float | None = None


class MarketTrade(BaseModel):
    symbol: str
    timestamp: datetime
    price: float = Field(gt=0)
    quantity: float = Field(gt=0)
    buyer_is_maker: bool


class OrderBookSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    version: int | None = None


class MultiTimeframeResult(BaseModel):
    symbol: str
    results: dict[Timeframe, CandleResult]
    errors: dict[Timeframe, str] = Field(default_factory=dict)
