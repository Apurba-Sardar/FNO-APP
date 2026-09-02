import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.execution.exceptions import StaleSignedRequest


class ClockService:
    """Epoch-ms clock with an explicit validity boundary for signed requests."""

    def __init__(self, clock: Callable[[], float] = time.time, *, max_skew_ms: int = 2_000):
        self._clock = clock
        self.max_skew_ms = max_skew_ms
        self._offset_ms = 0
        self.synchronized = True

    def get_current_epoch_ms(self) -> int:
        if not self.synchronized:
            raise StaleSignedRequest("system clock is not trusted")
        return int(self._clock() * 1000) + self._offset_ms

    def set_server_offset(self, server_epoch_ms: int, sampled_local_epoch_ms: int) -> None:
        offset = server_epoch_ms - sampled_local_epoch_ms
        if abs(offset) > self.max_skew_ms:
            self.synchronized = False
            raise StaleSignedRequest("clock offset exceeds configured tolerance")
        self._offset_ms = offset
        self.synchronized = True

    def assert_fresh(self, timestamp_ms: int, *, maximum_age_ms: int = 9_000) -> None:
        age = self.get_current_epoch_ms() - timestamp_ms
        if age < 0 or age > maximum_age_ms:
            raise StaleSignedRequest("signed request timestamp is stale")


@dataclass(frozen=True)
class SignedPayload:
    body: bytes
    signature: str
    headers: dict[str, str]


class CoinDCXSigner:
    """Signs and returns the exact compact JSON bytes that must be transmitted."""

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("CoinDCX API credentials are required")
        self._api_key = api_key
        self._secret = api_secret.encode("utf-8")

    @staticmethod
    def serialize(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def sign(self, payload: dict[str, Any]) -> SignedPayload:
        body = self.serialize(payload)
        signature = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return SignedPayload(
            body=body,
            signature=signature,
            headers={
                "Content-Type": "application/json",
                "X-AUTH-APIKEY": self._api_key,
                "X-AUTH-SIGNATURE": signature,
            },
        )
