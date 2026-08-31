from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoinDCXModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CoinDCXInstrument(CoinDCXModel):
    pair: str
    status: str
    settle_currency_short_name: str
    quote_currency_short_name: str
    underlying_currency_short_name: str | None = None
    kind: str | None = None
    price_increment: float | None = None
    quantity_increment: float | None = None
    min_quantity: float | None = None
    min_notional: float | None = None
    max_leverage_long: float | None = None
    max_leverage_short: float | None = None


class CoinDCXCandle(CoinDCXModel):
    time: Any = None
    open: Any = None
    high: Any = None
    low: Any = None
    close: Any = None
    volume: Any = None


class CoinDCXOrderBook(CoinDCXModel):
    ts: int | float
    vs: int | None = None
    bids: dict[str, str] = Field(default_factory=dict)
    asks: dict[str, str] = Field(default_factory=dict)


class CoinDCXTrade(CoinDCXModel):
    price: float
    quantity: float
    timestamp: int | float
    is_maker: bool


class CoinDCXPriceSnapshot(CoinDCXModel):
    ts: int | float
    vs: int | None = None
    prices: dict[str, dict] = Field(default_factory=dict)


class WebSocketCandle(CoinDCXModel):
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: int | float
    pair: str
    duration: str


class WebSocketTrade(CoinDCXModel):
    T: int | float
    p: float
    q: float
    m: int | bool
    s: str
    pr: str

    @field_validator("pr")
    @classmethod
    def futures_only(cls, value: str) -> str:
        if value.lower() not in {"f", "futures"}:
            raise ValueError("not a futures trade")
        return value
