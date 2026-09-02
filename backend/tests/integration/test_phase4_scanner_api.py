from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.config import Settings, get_settings
from app.scanner.config import ScannerConfig
from app.scanner.models import CandidateStatus, ScannerStatistics
from app.scanner.scanner import AllMarketScanner
from app.scanner.state import ScannerStateStore


class FakeRuntime:
    def __init__(self, state, stats):
        self.state = state
        self.stats = stats

    async def run_once(self):
        return self.stats

    async def start_scanning(self):
        self.state.scheduled = True

    async def stop_scanning(self):
        self.state.scheduled = False


def client(control_token=""):
    settings = Settings(
        _env_file=None,
        coindcx_websocket_enabled=False,
        market_scanner=ScannerConfig(control_token=control_token),
    )
    state = ScannerStateStore(None, 300, 900)
    scanner = AllMarketScanner(settings, settings.market_scanner, state, None)
    candidate = scanner._diagnostic_candidate(
        "B-BTC_USDT",
        datetime.now(UTC),
        CandidateStatus.FILTERED,
        "filtered_by_volume: fixture",
    )
    state.candidates[candidate.symbol] = candidate
    now = datetime.now(UTC)
    stats = ScannerStatistics(
        scan_started_at=now,
        scan_completed_at=now,
        total_markets=1,
        eligible_markets=0,
        filtered_markets=1,
        warning_markets=0,
        data_errors=0,
        stale_markets=0,
        insufficient_data_markets=0,
        processing_time_seconds=0.1,
        average_processing_time_ms=100,
    )
    state.stats = stats
    application = FastAPI()
    application.include_router(router)
    application.state.scanner_runtime = FakeRuntime(state, stats)
    application.state.market_data_runtime = SimpleNamespace()
    application.dependency_overrides[get_settings] = lambda: settings
    return TestClient(application)


def test_scanner_candidate_api_serializes_without_score_or_trade_signal():
    response = client().get("/api/v1/scanner/candidates")
    assert response.status_code == 200
    assert response.json()["items"][0]["symbol"] == "B-BTC_USDT"
    assert "score" not in response.text
    assert "trade_signal" not in response.text


def test_scanner_candidate_detail_and_stats_endpoints():
    api = client()
    assert api.get("/api/v1/scanner/candidates/B-BTC_USDT").status_code == 200
    assert api.get("/api/v1/scanner/candidates/B-MISSING_USDT").status_code == 404
    assert api.get("/api/v1/scanner/stats").json()["stats"]["total_markets"] == 1


def test_scanner_control_token_is_enforced_and_not_exposed():
    api = client("secret-token")
    assert api.post("/api/v1/scanner/run").status_code == 403
    assert (
        api.post(
            "/api/v1/scanner/run", headers={"x-scanner-control-token": "secret-token"}
        ).status_code
        == 200
    )
    config = api.get("/api/v1/scanner/config")
    assert "secret-token" not in config.text
