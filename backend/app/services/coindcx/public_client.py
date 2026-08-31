from typing import Any

import httpx
from pydantic import ValidationError

from .client import CoinDCXClient
from .constants import (
    ACTIVE_INSTRUMENTS_PATH,
    CANDLES_PATH,
    CURRENT_PRICES_PATH,
    INSTRUMENT_PATH,
    ORDERBOOK_DEPTHS,
    ORDERBOOK_PATH,
    REST_RESOLUTIONS,
    TRADES_PATH,
)
from .exceptions import CoinDCXMalformedResponseError
from .models import (
    CoinDCXCandle,
    CoinDCXInstrument,
    CoinDCXOrderBook,
    CoinDCXPriceSnapshot,
    CoinDCXTrade,
)


class CoinDCXPublicClient(CoinDCXClient):
    """Documented, unauthenticated futures market-data endpoints only."""

    def __init__(
        self,
        api_base_url: str,
        public_base_url: str,
        timeout: float = 10,
        *,
        requests_per_second: float = 15,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleeper=None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "timeout": timeout,
            "requests_per_second": requests_per_second,
            "max_retries": max_retries,
            "transport": transport,
        }
        if sleeper is not None:
            kwargs["sleeper"] = sleeper
        super().__init__(**kwargs)
        self.api_base_url = api_base_url.rstrip("/")
        self.public_base_url = public_base_url.rstrip("/")

    async def active_instruments(self) -> list[str]:
        data = await self.request_json(
            f"{self.api_base_url}{ACTIVE_INSTRUMENTS_PATH}",
            params={"margin_currency_short_name[]": "USDT"},
        )
        if not isinstance(data, list):
            raise CoinDCXMalformedResponseError("active instruments response is not a list")
        return sorted({str(pair) for pair in data})

    async def instrument(self, pair: str) -> CoinDCXInstrument:
        data = await self.request_json(
            f"{self.api_base_url}{INSTRUMENT_PATH}",
            params={"pair": pair, "margin_currency_short_name": "USDT"},
        )
        payload = data.get("instrument") if isinstance(data, dict) else None
        return self._validate(CoinDCXInstrument, payload, "instrument")

    async def candlesticks(
        self, pair: str, start_seconds: int, end_seconds: int, resolution: str
    ) -> list[CoinDCXCandle]:
        if resolution not in REST_RESOLUTIONS:
            raise ValueError(f"unsupported documented REST resolution: {resolution}")
        data = await self.request_json(
            f"{self.public_base_url}{CANDLES_PATH}",
            params={
                "pair": pair,
                "from": start_seconds,
                "to": end_seconds,
                "resolution": resolution,
                "pcode": "f",
            },
        )
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise CoinDCXMalformedResponseError("candlesticks data is not a list")
        return [self._validate(CoinDCXCandle, row, "candlestick") for row in rows]

    async def orderbook(self, pair: str, depth: int = 20) -> CoinDCXOrderBook:
        if depth not in ORDERBOOK_DEPTHS:
            raise ValueError("documented futures order-book depth must be 10, 20, or 50")
        data = await self.request_json(
            f"{self.public_base_url}{ORDERBOOK_PATH.format(pair=pair, depth=depth)}"
        )
        return self._validate(CoinDCXOrderBook, data, "order book")

    async def recent_trades(self, pair: str) -> list[CoinDCXTrade]:
        data = await self.request_json(f"{self.api_base_url}{TRADES_PATH}", params={"pair": pair})
        if not isinstance(data, list):
            raise CoinDCXMalformedResponseError("recent trades response is not a list")
        return [self._validate(CoinDCXTrade, row, "trade") for row in data]

    async def current_prices(self) -> CoinDCXPriceSnapshot:
        data = await self.request_json(f"{self.public_base_url}{CURRENT_PRICES_PATH}")
        return self._validate(CoinDCXPriceSnapshot, data, "current prices")

    @staticmethod
    def _validate(model, payload: Any, label: str):
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise CoinDCXMalformedResponseError(f"malformed CoinDCX {label}") from exc
