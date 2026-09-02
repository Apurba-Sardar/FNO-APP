from typing import Any

import httpx
import structlog

from app.execution.exceptions import UnknownOrderState

from .auth import ClockService, CoinDCXSigner
from .client import CoinDCXClient
from .constants import (
    FUTURES_CANCEL_ORDER_PATH,
    FUTURES_CREATE_ORDER_PATH,
    FUTURES_CREATE_TPSL_PATH,
    FUTURES_EXIT_POSITION_PATH,
    FUTURES_ORDERS_PATH,
    FUTURES_POSITIONS_PATH,
    FUTURES_TRADES_PATH,
    FUTURES_WALLETS_PATH,
)
from .exceptions import CoinDCXError, CoinDCXRateLimitError, CoinDCXTimeoutError


class AuthenticatedCoinDCXClient(CoinDCXClient):
    """Authenticated futures transport; submission ambiguity is never retried."""

    def __init__(self, *, api_base_url: str, api_key: str, api_secret: str, clock=None, **kwargs):
        super().__init__(**kwargs)
        self.api_base_url = api_base_url.rstrip("/")
        self.clock = clock or ClockService()
        self.signer = CoinDCXSigner(api_key, api_secret)
        self.log = structlog.get_logger()

    async def _signed_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        submission: bool = False,
        query: dict[str, Any] | None = None,
    ) -> Any:
        request = dict(payload or {})
        request["timestamp"] = self.clock.get_current_epoch_ms()
        signed = self.signer.sign(request)
        self.clock.assert_fresh(request["timestamp"])
        attempts = 1 if submission else self._max_retries + 1
        safe_path = httpx.URL(path).path
        for attempt in range(attempts):
            await self._throttle.acquire()
            self.request_count += 1
            self.log.info("COINDCX_AUTH_REQUEST", method=method, path=safe_path, attempt=attempt + 1)
            started_timestamp = request["timestamp"]
            try:
                response = await self._http.request(
                    method,
                    f"{self.api_base_url}{path}",
                    content=signed.body,
                    headers=signed.headers,
                    params=query,
                )
            except httpx.TimeoutException as exc:
                if submission:
                    raise UnknownOrderState("order submission timed out; reconciliation required") from exc
                if attempt + 1 >= attempts:
                    raise CoinDCXTimeoutError(f"CoinDCX request timed out: {safe_path}") from exc
                await self._sleep(0.25 * (2**attempt))
                request["timestamp"] = self.clock.get_current_epoch_ms()
                signed = self.signer.sign(request)
                continue
            except httpx.NetworkError as exc:
                if submission:
                    raise UnknownOrderState("order submission transport failed; reconciliation required") from exc
                if attempt + 1 >= attempts:
                    raise CoinDCXError(f"CoinDCX network failure: {safe_path}") from exc
                await self._sleep(0.25 * (2**attempt))
                request["timestamp"] = self.clock.get_current_epoch_ms()
                signed = self.signer.sign(request)
                continue
            if response.status_code == 429:
                self.log.warning("COINDCX_RATE_LIMIT", path=safe_path)
                if submission or attempt + 1 >= attempts:
                    raise CoinDCXRateLimitError(f"CoinDCX rate limit exceeded: {safe_path}")
                await self._sleep(self._retry_after(response, attempt))
                request["timestamp"] = self.clock.get_current_epoch_ms()
                signed = self.signer.sign(request)
                continue
            if response.status_code >= 500 and not submission and attempt + 1 < attempts:
                await self._sleep(0.25 * (2**attempt))
                request["timestamp"] = self.clock.get_current_epoch_ms()
                signed = self.signer.sign(request)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body_msg = response.text.strip()
                raise CoinDCXError(f"CoinDCX HTTP {response.status_code}: {safe_path} ({body_msg})") from exc
            self.log.info(
                "COINDCX_AUTH_RESPONSE",
                path=safe_path,
                status=response.status_code,
                request_timestamp=started_timestamp,
            )
            try:
                return response.json()
            except ValueError as exc:
                raise CoinDCXError(f"CoinDCX returned invalid JSON: {safe_path}") from exc
        raise AssertionError("unreachable")

    async def wallets(self):
        try:
            return await self._signed_request("POST", FUTURES_WALLETS_PATH, {})
        except Exception:
            try:
                return await self._signed_request("POST", FUTURES_WALLETS_PATH, {"margin_currency_short_name": ["USDT"]})
            except Exception:
                return await self._signed_request("POST", "/exchange/v1/users/balances", {})

    async def positions(self, *, pairs: str | None = None, position_ids: str | None = None):
        body: dict[str, Any] = {"page": 1, "size": 100}
        if pairs:
            body["pairs"] = pairs
        if position_ids:
            body["position_ids"] = position_ids
        try:
            return await self._signed_request("POST", FUTURES_POSITIONS_PATH, body)
        except Exception:
            try:
                return await self._signed_request("POST", FUTURES_POSITIONS_PATH, {})
            except Exception:
                return await self._signed_request("POST", FUTURES_POSITIONS_PATH, body | {"margin_currency_short_name": ["USDT"]})

    async def orders(self, *, status: str = "open,partially_filled,untriggered"):
        rows = []
        for side in ("buy", "sell"):
            response = await self._signed_request(
                "POST", FUTURES_ORDERS_PATH,
                {"status": status, "side": side, "page": "1", "size": "100", "margin_currency_short_name": ["USDT"]},
            )
            if not isinstance(response, list):
                raise CoinDCXError("CoinDCX futures orders response is not a list")
            rows.extend(response)
        return rows

    async def trades(self, *, pair: str, from_date: str, to_date: str, order_id: str | None = None):
        body: dict[str, Any] = {"pair": pair, "from_date": from_date, "to_date": to_date, "page": "1", "size": "100", "margin_currency_short_name": ["USDT"]}
        if order_id:
            body["order_id"] = order_id
        return await self._signed_request("POST", FUTURES_TRADES_PATH, body)

    async def create_order(self, order: dict[str, Any]):
        return await self._signed_request("POST", FUTURES_CREATE_ORDER_PATH, {"order": order}, submission=True)

    async def cancel_order(self, order_id: str):
        return await self._signed_request("POST", FUTURES_CANCEL_ORDER_PATH, {"id": order_id})

    async def exit_position(self, position_id: str):
        return await self._signed_request("POST", FUTURES_EXIT_POSITION_PATH, {"id": position_id}, submission=True)

    async def create_tpsl(self, position_id: str, stop: str, target: str):
        return await self._signed_request(
            "POST", FUTURES_CREATE_TPSL_PATH,
            {
                "id": position_id,
                "take_profit": {"stop_price": target, "order_type": "take_profit_market"},
                "stop_loss": {"stop_price": stop, "order_type": "stop_market"},
            },
            submission=True,
        )
