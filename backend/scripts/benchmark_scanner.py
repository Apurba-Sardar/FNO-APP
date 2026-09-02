"""Synthetic Phase 4 benchmark for 100 markets x 6 timeframes."""

import asyncio
import json
import time
import tracemalloc
from datetime import UTC, datetime

from app.config import Settings
from app.domain.market import Timeframe
from app.market_data.models import (
    CandleResult,
    Market,
    MarketType,
    MultiTimeframeResult,
    NormalizedCandle,
)
from app.market_data.normalization import TIMEFRAME_DURATION
from app.scanner.config import ScannerConfig
from app.scanner.scanner import AllMarketScanner
from app.scanner.state import ScannerStateStore
from app.services.coindcx.models import CoinDCXOrderBook


def frames(symbol: str) -> MultiTimeframeResult:
    results = {}
    wave = (0, 0.4, 0.8, 0.4, 0, -0.4, -0.8, -0.4)
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        start = datetime.now(UTC) - duration * 219
        rows = []
        for index in range(220):
            close = 100 + index * 0.05 + wave[index % len(wave)]
            rows.append(
                NormalizedCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=start + duration * index,
                    open=close - 0.1,
                    high=close + 0.5,
                    low=close - 0.5,
                    close=close,
                    volume=100 + index % 20,
                )
            )
        results[timeframe] = CandleResult(symbol=symbol, timeframe=timeframe, candles=rows)
    return MultiTimeframeResult(symbol=symbol, results=results)


class FakeClient:
    def __init__(self) -> None:
        self.request_count = 2  # one discovery and one current-price snapshot

    async def orderbook(self, _symbol, _depth):
        self.request_count += 1
        now = int(datetime.now(UTC).timestamp() * 1000)
        return CoinDCXOrderBook(
            ts=now,
            bids={"99.99": "2000", "99.98": "2000"},
            asks={"100.01": "2000", "100.02": "2000"},
        )


class FakeMarketData:
    def __init__(self, client, datasets):
        self.client = client
        self.datasets = datasets

    async def get_multi_timeframe_candles(self, symbol, _timeframes, _limit):
        self.client.request_count += 6
        return self.datasets[symbol]


async def main() -> None:
    tracemalloc.start()
    symbols = [f"B-TEST{index}_USDT" for index in range(100)]
    datasets = {symbol: frames(symbol) for symbol in symbols}
    fixture_memory, _ = tracemalloc.get_traced_memory()
    settings = Settings(_env_file=None, coindcx_websocket_enabled=False)
    config = ScannerConfig(max_concurrency=5)
    state = ScannerStateStore(None, config.interval_seconds, config.state_ttl_seconds)
    scanner = AllMarketScanner(settings, config, state, None)
    client = FakeClient()
    market_data = FakeMarketData(client, datasets)
    semaphore = asyncio.Semaphore(config.max_concurrency)
    timestamp = datetime.now(UTC)

    async def one(symbol):
        async with semaphore:
            return await scanner._scan_market(
                Market(
                    symbol=symbol,
                    base_asset=symbol.removeprefix("B-").removesuffix("_USDT"),
                    quote_asset="USDT",
                    market_type=MarketType.FUTURES,
                    status="active",
                ),
                {"ls": 110, "v": 1_000_000, "pc": 1.2},
                timestamp,
                client,
                market_data,
                timestamp,
            )

    started = time.perf_counter()
    candidates = await asyncio.gather(*(one(symbol) for symbol in symbols))
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    failed = sum(candidate.status.value in {"data_error", "stale"} for candidate in candidates)
    print(
        json.dumps(
            {
                "markets": len(symbols),
                "timeframes_per_market": 6,
                "candles_per_timeframe": 220,
                "max_concurrency": config.max_concurrency,
                "total_scan_seconds": round(elapsed, 4),
                "analysis_seconds": round(scanner._analysis_seconds, 4),
                "average_symbol_ms": round(elapsed / len(symbols) * 1000, 4),
                "mock_api_requests": client.request_count,
                "failed_symbols": failed,
                "fixture_memory_mib": round(fixture_memory / 1024 / 1024, 4),
                "traced_peak_mib": round(peak / 1024 / 1024, 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
