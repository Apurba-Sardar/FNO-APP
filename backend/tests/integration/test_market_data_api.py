from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.config import Settings, get_settings
from app.db.session import get_session
from app.services.coindcx.models import CoinDCXCandle


class FakeStore:
    async def get_candles(self, *_args):
        return None

    async def set_candles(self, *_args):
        return None

    async def set_latest_candle(self, *_args):
        return None

    async def get_ticker(self, *_args):
        return None


class FakeRuntime:
    def __init__(self):
        self.store = FakeStore()
        self.last_market_update = None

    def record_update(self, timestamp):
        self.last_market_update = timestamp


class FakeSession:
    async def execute(self, *_args, **_kwargs):
        raise ConnectionError("database intentionally absent")

    async def commit(self):
        return None

    async def rollback(self):
        return None


class FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def active_instruments(self):
        return ["B-BTC_USDT"]

    async def candlesticks(self, *_args):
        timestamp = int(datetime.now(UTC).timestamp() // 300 * 300 * 1000)
        return [
            CoinDCXCandle(
                time=timestamp,
                open=100,
                high=110,
                low=90,
                close=105,
                volume=10,
            )
        ]


def make_client(monkeypatch) -> TestClient:
    application = FastAPI()
    application.include_router(routes.router)
    application.state.market_data_runtime = FakeRuntime()
    settings = Settings(
        _env_file=None,
        coindcx_api_secret="must-never-appear",
        coindcx_websocket_enabled=False,
    )
    application.dependency_overrides[get_settings] = lambda: settings

    async def session_override():
        yield FakeSession()

    application.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(routes, "create_market_data_client", lambda _settings: FakeClient())
    return TestClient(application)


def test_markets_endpoint_returns_normalized_models(monkeypatch):
    response = make_client(monkeypatch).get("/api/v1/markets")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0] == {
        "symbol": "B-BTC_USDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "market_type": "futures",
        "status": "active",
        "contract_kind": None,
        "price_precision": None,
        "quantity_precision": None,
        "min_quantity": None,
        "min_notional": None,
        "tick_size": None,
        "step_size": None,
    }
    assert "must-never-appear" not in response.text


def test_candles_endpoint_returns_normalized_candles(monkeypatch):
    response = make_client(monkeypatch).get(
        "/api/v1/markets/B-BTC_USDT/candles?timeframe=5m&limit=1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "B-BTC_USDT"
    assert body["timeframe"] == "5m"
    assert body["candles"][0]["close"] == 105
    assert not body["stale"]


def test_analysis_endpoint_serializes_typed_analysis_without_trade_decisions(monkeypatch):
    response = make_client(monkeypatch).get("/api/v1/analysis/B-BTC_USDT/5m")
    assert response.status_code == 200
    body = response.json()
    frame = body["timeframes"]["5m"]
    assert body["symbol"] == "B-BTC_USDT"
    assert frame["indicators"]["close"] == 105
    assert frame["indicators"]["ema200"] is None
    assert frame["data_quality"]["sufficient_data"] is False
    assert "buy" not in response.text.lower()
    assert "sell" not in response.text.lower()


def test_analysis_endpoint_validates_timeframe_filter(monkeypatch):
    response = make_client(monkeypatch).get("/api/v1/analysis/B-BTC_USDT?timeframes=1W,1D,invalid")
    assert response.status_code == 422
