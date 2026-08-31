import httpx
import pytest

from app.services.coindcx.exceptions import CoinDCXTimeoutError
from app.services.coindcx.public_client import CoinDCXPublicClient


async def no_sleep(_delay):
    return None


async def test_timeout_is_retried_then_normalized():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    client = CoinDCXPublicClient(
        "https://api.test",
        "https://public.test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleeper=no_sleep,
    )
    with pytest.raises(CoinDCXTimeoutError):
        await client.active_instruments()
    await client.close()


async def test_429_honors_retry_and_recovers():
    calls = 0
    delays = []

    def handler(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=["B-BTC_USDT"])

    async def sleeper(delay):
        delays.append(delay)

    client = CoinDCXPublicClient(
        "https://api.test",
        "https://public.test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleeper=sleeper,
    )
    assert await client.active_instruments() == ["B-BTC_USDT"]
    assert calls == 2
    assert delays == [0]
    await client.close()
