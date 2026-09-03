import hashlib
import hmac
import json

import httpx
import pytest

from app.execution.config import ExecutionStage, LiveExecutionConfig
from app.execution.exceptions import StaleSignedRequest, UnknownOrderState
from app.services.coindcx.auth import ClockService, CoinDCXSigner
from app.services.coindcx.authenticated_client import AuthenticatedCoinDCXClient
from app.services.coindcx.exceptions import CoinDCXRateLimitError


def test_live_defaults_are_paper_only_and_submission_disabled():
    config = LiveExecutionConfig()
    assert config.stage == ExecutionStage.PAPER_ONLY
    assert config.submission_configured is False
    assert config.auto_execution is False
    assert "confirmation" not in config.public_dict()
    assert "operator_token" not in config.public_dict()


def test_auto_execution_requires_stage_five():
    with pytest.raises(ValueError):
        LiveExecutionConfig(auto_execution=True, stage=4)
    with pytest.raises(ValueError):
        LiveExecutionConfig(auto_execution=False, stage=5)


def test_signer_uses_exact_compact_json_bytes_and_required_headers():
    payload = {"timestamp": 123, "order": {"side": "buy", "pair": "B-BTC_USDT"}}
    signed = CoinDCXSigner("public-key", "secret-value").sign(payload)
    assert signed.body == json.dumps(payload, separators=(",", ":")).encode()
    assert signed.signature == hmac.new(b"secret-value", signed.body, hashlib.sha256).hexdigest()
    assert signed.headers["X-AUTH-APIKEY"] == "public-key"
    assert signed.headers["X-AUTH-SIGNATURE"] == signed.signature
    assert b"secret-value" not in signed.body


def test_clock_rejects_stale_and_untrusted_requests():
    clock = ClockService(lambda: 100.0)
    with pytest.raises(StaleSignedRequest):
        clock.assert_fresh(90_000)
    with pytest.raises(StaleSignedRequest):
        clock.set_server_offset(120_000, 100_000)
    with pytest.raises(StaleSignedRequest):
        clock.get_current_epoch_ms()


@pytest.mark.asyncio
async def test_authenticated_client_sends_the_signed_bytes_unchanged():
    captured = {}

    def handler(request: httpx.Request):
        captured["body"] = request.content
        captured["headers"] = request.headers
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json=[{"id": "wallet", "currency_short_name": "USDT"}])

    client = AuthenticatedCoinDCXClient(
        api_base_url="https://api.coindcx.test",
        api_key="key",
        api_secret="secret",
        clock=ClockService(lambda: 1_700_000_000.0),
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    try:
        await client.wallets()
    finally:
        await client.close()
    assert captured["body"] == b'{"timestamp":1700000000000}'
    assert captured["method"] == "GET"
    assert captured["path"] == "/exchange/v1/derivatives/futures/wallets"
    expected = hmac.new(b"secret", captured["body"], hashlib.sha256).hexdigest()
    assert captured["headers"]["x-auth-signature"] == expected
    assert "secret" not in repr(captured)


@pytest.mark.asyncio
async def test_order_submission_timeout_is_unknown_and_never_retried():
    calls = 0

    def handler(_: httpx.Request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("after send")

    client = AuthenticatedCoinDCXClient(
        api_base_url="https://api.coindcx.test", api_key="key", api_secret="secret",
        clock=ClockService(lambda: 1_700_000_000.0), transport=httpx.MockTransport(handler),
        max_retries=3,
    )
    try:
        with pytest.raises(UnknownOrderState):
            await client.create_order({"side": "buy", "pair": "B-BTC_USDT"})
    finally:
        await client.close()
    assert calls == 1


@pytest.mark.asyncio
async def test_submission_rate_limit_is_not_retried():
    calls = 0

    def handler(_: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "1"})

    client = AuthenticatedCoinDCXClient(
        api_base_url="https://api.coindcx.test", api_key="key", api_secret="secret",
        clock=ClockService(lambda: 1_700_000_000.0), transport=httpx.MockTransport(handler),
        max_retries=3,
    )
    try:
        with pytest.raises(CoinDCXRateLimitError):
            await client.create_order({"side": "buy", "pair": "B-BTC_USDT"})
    finally:
        await client.close()
    assert calls == 1
