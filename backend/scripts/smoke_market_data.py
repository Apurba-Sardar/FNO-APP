"""Live, read-only REST and public WebSocket smoke test. Uses no credentials."""

import asyncio
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.services.coindcx.public_client import CoinDCXPublicClient
from app.services.coindcx.websocket import CoinDCXWebSocketClient


class FirstTickerStore:
    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.ticker = None

    async def set_ticker(self, ticker) -> None:
        self.ticker = ticker
        self.event.set()


async def main() -> None:
    settings = get_settings()
    async with CoinDCXPublicClient(
        settings.coindcx_api_base_url,
        settings.coindcx_public_base_url,
        settings.request_timeout_seconds,
        requests_per_second=settings.coindcx_requests_per_second,
        max_retries=settings.coindcx_max_retries,
    ) as client:
        symbols = await client.active_instruments()
        sample_symbol = "B-BTC_USDT" if "B-BTC_USDT" in symbols else symbols[0]
        instrument = await client.instrument(sample_symbol)
        now = datetime.now(UTC)
        candles = await client.candlesticks(
            instrument.pair,
            int((now - timedelta(days=2)).timestamp()),
            int(now.timestamp()),
            "60",
        )

    store = FirstTickerStore()
    websocket = CoinDCXWebSocketClient(settings.coindcx_websocket_url, store=store)
    await websocket.subscribe_current_prices()
    task = asyncio.create_task(websocket.run_forever())
    try:
        await asyncio.wait_for(store.event.wait(), timeout=20)
        print(
            {
                "markets": len(symbols),
                "sample_market": instrument.pair,
                "sample_candles": len(candles),
                "websocket_status": websocket.status.value,
                "websocket_symbol": store.ticker.symbol,
                "websocket_timestamp": store.ticker.timestamp.isoformat(),
            }
        )
    finally:
        await websocket.shutdown()
        await asyncio.wait_for(task, timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
