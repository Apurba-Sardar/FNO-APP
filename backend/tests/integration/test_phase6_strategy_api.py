from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.config import Settings, get_settings
from app.strategy.config import StrategyConfig
from app.strategy.state import StrategyRuntime, StrategyState
from tests.phase6_fixtures import strategy_fixture


async def build_client(control_token: str = "") -> TestClient:
    config = StrategyConfig(control_token=control_token, minimum_setup_quality=0)
    market, opportunity, _, _, engine = strategy_fixture(config=config)
    scanner_state = SimpleNamespace(candidates={market.symbol: market})
    opportunity_state = SimpleNamespace(opportunities={opportunity.symbol: opportunity})
    runtime = StrategyRuntime(
        scanner_state,
        opportunity_state,
        StrategyState(None, config),
        engine,
        config,
    )
    await runtime.evaluate_all(evaluation_timestamp=market.scan_timestamp)
    settings = Settings(_env_file=None, coindcx_websocket_enabled=False, strategy=config)
    application = FastAPI()
    application.include_router(router)
    application.state.strategy_runtime = runtime
    application.dependency_overrides[get_settings] = lambda: settings
    return TestClient(application)


async def test_strategy_read_endpoints_return_normalized_models():
    api = await build_client()
    listing = api.get("/api/v1/setups")
    assert listing.status_code == 200
    assert listing.json()["count"] == 2
    symbol = listing.json()["items"][0]["symbol"]
    detail = api.get(f"/api/v1/setups/{symbol}")
    assert detail.status_code == 200
    assert set(detail.json()["results"]) == {"trend_pullback", "breakout"}
    assert detail.json()["chart"]
    assert api.get(f"/api/v1/strategies/{symbol}/trend_pullback").status_code == 200
    assert api.get(f"/api/v1/strategies/{symbol}/trend-pullback").status_code == 200
    assert api.get(f"/api/v1/strategies/{symbol}/breakout").status_code == 200
    assert api.get("/api/v1/setups/B-MISSING_USDT").status_code == 404


async def test_strategy_evaluation_control_and_config_redaction():
    api = await build_client("phase6-secret")
    assert api.post("/api/v1/strategies/evaluate", json={}).status_code == 403
    assert (
        api.post(
            "/api/v1/strategies/evaluate",
            json={},
            headers={"x-strategy-control-token": "phase6-secret"},
        ).status_code
        == 200
    )
    config = api.get("/api/v1/strategies/config")
    assert config.status_code == 200
    assert "phase6-secret" not in config.text


async def test_strategy_api_has_no_execution_contract():
    api = await build_client()
    payload = api.get("/api/v1/setups").text.lower()
    for forbidden in ("order_id", "quantity", "leverage", "win_probability", "take_profit"):
        assert forbidden not in payload
