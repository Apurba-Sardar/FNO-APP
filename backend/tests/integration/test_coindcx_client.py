import httpx
import pytest

from app.clients.coindcx import CoinDCXPublicClient


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("active_instruments"):
        assert request.url.params["margin_currency_short_name[]"] == "USDT"
        return httpx.Response(200, json=["B-ETH_USDT", "B-BTC_USDT", "B-OTHER_INR"])
    if path.endswith("/instrument"):
        return httpx.Response(
            200,
            json={
                "instrument": {
                    "pair": "B-BTC_USDT",
                    "status": "active",
                    "settle_currency_short_name": "USDT",
                    "quote_currency_short_name": "USDT",
                    "quantity_increment": 0.001,
                    "price_increment": 0.1,
                    "min_notional": 60,
                    "max_leverage_long": 20,
                    "max_leverage_short": 20,
                }
            },
        )
    if path.endswith("candlesticks"):
        assert request.url.params["pcode"] == "f"
        return httpx.Response(
            200,
            json={
                "s": "ok",
                "data": [
                    {
                        "time": 1735689600000,
                        "open": 100,
                        "high": 110,
                        "low": 90,
                        "close": 105,
                        "volume": 12,
                    }
                ],
            },
        )
    if "orderbook" in path:
        return httpx.Response(
            200, json={"ts": 1735689600000, "bids": {"100": "2"}, "asks": {"101": "3"}}
        )
    return httpx.Response(404)


@pytest.fixture
def client():
    return CoinDCXPublicClient(
        "https://api.test", "https://public.test", transport=httpx.MockTransport(handler)
    )


async def test_public_market_endpoints_are_parsed(client):
    assert await client.get_active_instruments() == ["B-BTC_USDT", "B-ETH_USDT"]
    instrument = await client.get_instrument("B-BTC_USDT")
    assert instrument.status == "active"
    assert instrument.quantity_increment == 0.001
    assert instrument.max_leverage == 20
    candles = await client.get_candles("B-BTC_USDT", 1, 2, "5")
    assert candles[0].close == 105
    book = await client.get_order_book("B-BTC_USDT", 20)
    assert book.bids == [(100, 2)]
    await client.close()


async def test_undocumented_depth_is_rejected_before_request(client):
    with pytest.raises(ValueError):
        await client.get_order_book("B-BTC_USDT", 100)
    await client.close()
