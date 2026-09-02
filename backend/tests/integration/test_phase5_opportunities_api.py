from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.config import Settings, get_settings
from app.scoring.config import ScoringConfig
from app.scoring.engine import OpportunityScoringEngine
from app.scoring.state import OpportunityRuntime, OpportunityState
from tests.phase5_fixtures import candidate


def client(control_token: str = "") -> TestClient:
    settings = Settings(
        _env_file=None,
        coindcx_websocket_enabled=False,
        scoring=ScoringConfig(control_token=control_token),
    )
    scanner_state = SimpleNamespace(
        candidates={
            "B-BULL_USDT": candidate(0.2, "B-BULL_USDT"),
            "B-BEAR_USDT": candidate(-0.2, "B-BEAR_USDT"),
        }
    )
    state = OpportunityState(None, settings.scoring)
    runtime = OpportunityRuntime(scanner_state, state, OpportunityScoringEngine(settings.scoring))
    application = FastAPI()
    application.include_router(router)
    application.state.opportunity_runtime = runtime
    application.dependency_overrides[get_settings] = lambda: settings
    api = TestClient(application)
    response = api.post(
        "/api/v1/opportunities/recalculate",
        headers={"x-opportunity-control-token": control_token} if control_token else {},
    )
    assert response.status_code == 200
    return api


def test_opportunity_endpoints_serialize_ranked_explanations():
    api = client()
    listing = api.get("/api/v1/opportunities?eligible_only=true")
    assert listing.status_code == 200
    assert listing.json()["count"] == 2
    assert listing.json()["items"][0]["current_rank"] == 1
    assert api.get("/api/v1/opportunities/top").json()["count"] == 2
    detail = api.get("/api/v1/opportunities/B-BULL_USDT")
    assert detail.status_code == 200
    assert len(detail.json()["factors"]) == 10
    assert "explanation_summary" in detail.json()
    assert api.get("/api/v1/opportunities/stats").json()["stats"]["markets_analyzed"] == 2
    assert api.get("/api/v1/opportunities/B-MISSING_USDT").status_code == 404


def test_recalculation_control_token_and_config_redaction():
    api = client("phase5-secret")
    assert api.post("/api/v1/opportunities/recalculate").status_code == 403
    assert (
        api.post(
            "/api/v1/opportunities/recalculate",
            headers={"x-opportunity-control-token": "phase5-secret"},
        ).status_code
        == 200
    )
    response = api.get("/api/v1/opportunities/config")
    assert response.status_code == 200
    assert "phase5-secret" not in response.text
    assert sum(response.json()["weights"].values()) == 100


def test_scoring_api_contains_no_probability_or_execution_fields():
    response = client().get("/api/v1/opportunities/B-BULL_USDT")
    payload = response.text.lower()
    assert "win_probability" not in payload
    assert "profit_probability" not in payload
    assert "create_order" not in payload
    assert "order_id" not in payload
    assert "trade_signal" not in payload
