import asyncio
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.scanner.config import ScannerConfig
from app.scanner.exceptions import ScanAlreadyRunning
from app.scanner.models import CandidateStatus
from app.scanner.scanner import AllMarketScanner
from app.scanner.state import ScannerStateStore
from app.services.coindcx.models import CoinDCXPriceSnapshot


class FakeCache:
    pass


class FakeClient:
    def __init__(self, count=101):
        self.symbols = [f"B-TEST{index}_USDT" for index in range(count)]
        self.request_count = 2

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def active_instruments(self):
        return self.symbols

    async def current_prices(self):
        now = int(datetime.now(UTC).timestamp() * 1000)
        return CoinDCXPriceSnapshot(
            ts=now,
            prices={symbol: {"ls": 100, "v": 1_000_000} for symbol in self.symbols},
        )


class IsolationScanner(AllMarketScanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active = 0
        self.maximum_active = 0

    async def _scan_market(self, market, *_args):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0)
        self.active -= 1
        if market.symbol == "B-TEST50_USDT":
            raise TimeoutError("mock timeout")
        return self._diagnostic_candidate(
            market.symbol,
            datetime.now(UTC),
            CandidateStatus.FILTERED,
            "filtered_by_volume: fixture",
        )


def scanner(scanner_type=IsolationScanner, count=101, concurrency=4):
    settings = Settings(_env_file=None, coindcx_websocket_enabled=False)
    config = ScannerConfig(max_concurrency=concurrency)
    state = ScannerStateStore(None, config.interval_seconds, config.state_ttl_seconds)
    fake = FakeClient(count)
    return scanner_type(settings, config, state, FakeCache(), client_factory=lambda: fake)


@pytest.mark.asyncio
async def test_101_market_failure_isolation_and_controlled_concurrency():
    service = scanner()
    stats = await service.scan_all_markets()
    assert stats.total_markets == 101
    assert stats.data_errors == 1
    assert stats.filtered_markets == 100
    assert len(service.state.candidates) == 101
    assert service.maximum_active <= 4
    assert service.state.candidates["B-TEST50_USDT"].status == "data_error"


class SlowScanner(AllMarketScanner):
    async def _run_cycle(self, _timestamp):
        await asyncio.sleep(0.05)
        return [], 0, 0


@pytest.mark.asyncio
async def test_duplicate_scan_is_rejected():
    service = scanner(SlowScanner, count=0)
    first = asyncio.create_task(service.scan_all_markets())
    await asyncio.sleep(0)
    with pytest.raises(ScanAlreadyRunning):
        await service.scan_all_markets()
    await first


@pytest.mark.asyncio
async def test_scanner_statistics_count_filter_reasons():
    service = scanner(count=3)
    stats = await service.scan_all_markets()
    assert stats.filter_counts["filtered_by_volume"] == 3
    assert stats.average_processing_time_ms >= 0


@pytest.mark.asyncio
async def test_latest_state_replaces_disappeared_markets():
    service = scanner(count=3)
    await service.scan_all_markets()
    assert len(service.state.candidates) == 3
    service.client_factory = lambda: FakeClient(2)
    await service.scan_all_markets()
    assert len(service.state.candidates) == 2
