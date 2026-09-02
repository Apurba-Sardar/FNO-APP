from datetime import timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.config import Settings, get_settings
from app.risk.config import RiskConfig
from app.risk.engine import RiskEngine
from app.risk.models import RiskLockState
from app.risk.state import RiskRuntime, RiskStateStore
from app.strategy.models import StrategyName
from tests.phase6_fixtures import strategy_fixture
from tests.phase7_fixtures import account, instrument, setup


async def client(control_token: str = "") -> TestClient:
    config = RiskConfig(control_token=control_token)
    market, opportunity, _, _, strategy_engine = strategy_fixture()
    timestamp = market.scan_timestamp
    analysis = strategy_engine.evaluate(opportunity, market, timestamp)
    triggered = setup(
        symbol=market.symbol,
        evaluation_timestamp=timestamp,
        expires_at=timestamp + timedelta(minutes=60),
    )
    analysis.current_price = 100.05
    analysis.atr = 1
    analysis.spread_percent = 0.02
    analysis.estimated_slippage_percent = 0.05
    analysis.results[StrategyName.TREND_PULLBACK] = triggered
    analysis.best_setup = triggered
    market.market.data_timestamp = timestamp - timedelta(seconds=30)
    market.liquidity.orderbook_timestamp = timestamp - timedelta(seconds=30)
    market.instrument = instrument(symbol=market.symbol)
    scanner_state = SimpleNamespace(candidates={market.symbol: market})
    strategy_state = SimpleNamespace(analyses={market.symbol: analysis})
    state = RiskStateStore(None, config)
    runtime = RiskRuntime(scanner_state, strategy_state, state, RiskEngine(config), config)
    await runtime.evaluate_all(evaluation_timestamp=timestamp, account=account(timestamp=timestamp))
    settings = Settings(_env_file=None, coindcx_websocket_enabled=False, risk=config)
    application = FastAPI()
    application.include_router(router)
    application.state.risk_runtime = runtime
    application.dependency_overrides[get_settings] = lambda: settings
    return TestClient(application)


async def test_risk_read_endpoints_return_explainable_decisions():
    api = await client()
    rows = api.get("/api/v1/risk/decisions")
    assert rows.status_code == 200
    assert rows.json()["count"] == 1
    assert rows.json()["items"][0]["allowed"]
    symbol = rows.json()["items"][0]["symbol"]
    detail = api.get(f"/api/v1/risk/check/{symbol}")
    assert detail.status_code == 200
    decision = detail.json()["decisions"]["trend_pullback"]
    assert decision["maximum_loss"] <= decision["risk_amount"]
    assert len(decision["checks"]) >= 20
    assert api.get("/api/v1/risk/check/B-MISSING_USDT").status_code == 404


async def test_recalculate_persists_normalized_account_state_and_lock():
    api = await client()
    snapshot = account()
    body = {
        "account": snapshot.model_dump(mode="json"),
        "evaluation_timestamp": snapshot.timestamp.isoformat(),
    }
    result = api.post("/api/v1/risk/recalculate", json=body)
    assert result.status_code == 200
    status = api.get("/api/v1/risk/status").json()["state"]
    assert status["trading_lock"] == RiskLockState.OPEN
    assert status["account"]["account_equity"] == 100_000


async def test_control_token_config_redaction_and_no_execution_routes():
    api = await client("phase7-secret")
    assert api.post("/api/v1/risk/evaluate", json={}).status_code == 403
    assert (
        api.post(
            "/api/v1/risk/evaluate",
            json={},
            headers={"x-risk-control-token": "phase7-secret"},
        ).status_code
        == 200
    )
    config = api.get("/api/v1/risk/config")
    assert config.status_code == 200
    assert "phase7-secret" not in config.text
    paths = api.get("/openapi.json").json()["paths"]
    for forbidden in ("/api/v1/order", "/api/v1/trade", "/api/v1/execute"):
        assert forbidden not in paths
