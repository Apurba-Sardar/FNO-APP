from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Timeframe(StrEnum):
    WEEK_1 = "1w"
    DAY_1 = "1d"
    HOUR_4 = "4h"
    HOUR_1 = "1h"
    MINUTE_15 = "15m"
    MINUTE_5 = "5m"


class Candle(BaseModel):
    time: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Candle":
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC range")
        return self

    @classmethod
    def from_api(cls, row: dict) -> "Candle":
        return cls(
            time=datetime.fromtimestamp(float(row["time"]) / 1000, tz=UTC),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )


class OrderBook(BaseModel):
    pair: str
    timestamp: datetime
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]


class OrderBookMetrics(BaseModel):
    bid_volume: float
    ask_volume: float
    imbalance: float
    spread_bps: float
    execution_depth_quote: float
    estimated_slippage_bps: float


class Instrument(BaseModel):
    pair: str
    status: str = "active"
    margin_currency: str = "USDT"
    quote_currency: str = "USDT"
    underlying_currency: str | None = None
    min_quantity: float | None = None
    quantity_precision: int | None = None
    quantity_increment: float | None = None
    price_increment: float | None = None
    min_notional: float | None = None
    max_leverage: float | None = None
