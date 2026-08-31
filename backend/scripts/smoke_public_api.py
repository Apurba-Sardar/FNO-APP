"""Read-only live smoke test. It never accesses credentials or private endpoints."""

import asyncio
from datetime import UTC, datetime, timedelta

from app.clients.coindcx import CoinDCXPublicClient
from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    async with CoinDCXPublicClient(
        settings.coindcx_api_base_url,
        settings.coindcx_public_base_url,
        settings.request_timeout_seconds,
    ) as client:
        pairs = await client.get_active_instruments()
        pair = pairs[0]
        instrument = await client.get_instrument(pair)
        book = await client.get_order_book(pair, 10)
        now = datetime.now(UTC)
        candles = await client.get_candles(
            pair, int((now - timedelta(days=2)).timestamp()), int(now.timestamp()), "60"
        )
        print(
            {
                "instrument_count": len(pairs),
                "sample_pair": pair,
                "sample_status": instrument.status,
                "book_levels": (len(book.bids), len(book.asks)),
                "candle_count": len(candles),
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
