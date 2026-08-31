import asyncio
from collections import deque
from time import monotonic
from typing import Any, Self

import httpx
import structlog

from .exceptions import (
    CoinDCXError,
    CoinDCXMalformedResponseError,
    CoinDCXRateLimitError,
    CoinDCXTimeoutError,
)


class AsyncRequestThrottle:
    def __init__(self, requests_per_second: float = 15) -> None:
        self.limit = requests_per_second
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = monotonic()
                while self._timestamps and now - self._timestamps[0] >= 1:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.limit:
                    self._timestamps.append(now)
                    return
                await asyncio.sleep(max(0, 1 - (now - self._timestamps[0])))


class CoinDCXClient:
    """Centralized transport, throttle, timeout, retry, and safe structured logging."""

    def __init__(
        self,
        *,
        timeout: float = 10,
        requests_per_second: float = 15,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleeper=asyncio.sleep,
    ) -> None:
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport)
        self._throttle = AsyncRequestThrottle(requests_per_second)
        self._max_retries = max_retries
        self._sleep = sleeper
        self.log = structlog.get_logger()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def request_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        safe_path = httpx.URL(url).path
        for attempt in range(self._max_retries + 1):
            await self._throttle.acquire()
            self.log.info("COINDCX_REQUEST", method="GET", path=safe_path, attempt=attempt + 1)
            try:
                response = await self._http.get(url, params=params)
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise CoinDCXTimeoutError(f"CoinDCX request timed out: {safe_path}") from exc
                await self._sleep(0.25 * (2**attempt))
                continue
            except httpx.NetworkError as exc:
                if attempt >= self._max_retries:
                    raise CoinDCXError(f"CoinDCX network failure: {safe_path}") from exc
                await self._sleep(0.25 * (2**attempt))
                continue

            if response.status_code == 429:
                retry_after = self._retry_after(response, attempt)
                self.log.warning("COINDCX_RATE_LIMIT", path=safe_path, retry_after=retry_after)
                if attempt >= self._max_retries:
                    raise CoinDCXRateLimitError(f"CoinDCX rate limit exceeded: {safe_path}")
                await self._sleep(retry_after)
                continue
            if response.status_code >= 500:
                self.log.warning(
                    "COINDCX_RESPONSE_ERROR", path=safe_path, status=response.status_code
                )
                if attempt < self._max_retries:
                    await self._sleep(0.25 * (2**attempt))
                    continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise CoinDCXError(f"CoinDCX HTTP {response.status_code}: {safe_path}") from exc
            try:
                return response.json()
            except ValueError as exc:
                raise CoinDCXMalformedResponseError(
                    f"CoinDCX returned invalid JSON: {safe_path}"
                ) from exc
        raise AssertionError("unreachable")

    @staticmethod
    def _retry_after(response: httpx.Response, attempt: int) -> float:
        try:
            return max(float(response.headers.get("Retry-After", "")), 0)
        except ValueError:
            return min(0.5 * (2**attempt), 8)
