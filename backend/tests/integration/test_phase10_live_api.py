from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.config import Settings, get_settings
from app.execution.config import LiveExecutionConfig
from app.execution.models import LiveAccount, LiveRuntimeState


class Runtime:
    def __init__(self):
        self.config = LiveExecutionConfig()
        self.account = LiveAccount()
        self.positions = {}
        self.orders = {}
        self.intents = {}
        self.market_runtime = SimpleNamespace(websocket=SimpleNamespace(health=lambda: {"status": "disabled"}))
        self.client = None
        self.last_api_error = None
        self.risk_runtime = None

    def status(self):
        return {"execution_mode": "paper", "stage": 0, "runtime_state": LiveRuntimeState.DISABLED, "live_enabled": False}


def api():
    application = FastAPI()
    application.include_router(router)
    application.state.live_runtime = Runtime()
    settings = Settings(live_operator_token="operator", live_emergency_token="emergency")
    application.dependency_overrides[get_settings] = lambda: settings
    return TestClient(application)


def test_all_live_state_endpoints_require_backend_authorization():
    http = api()
    for path in ["status", "health", "account", "positions", "orders", "trades", "exposure", "risk", "config"]:
        assert http.get(f"/api/v1/live/{path}").status_code == 403
    response = http.get("/api/v1/live/status", headers={"x-live-operator-token": "operator"})
    assert response.status_code == 200
    assert response.json()["stage"] == 0


def test_frontend_cannot_override_execution_quantity_stop_target_or_leverage():
    http = api()
    response = http.post(
        "/api/v1/live/execute",
        headers={"x-live-operator-token": "operator"},
        json={"setup_id": "setup", "quantity": 999, "stop": 1, "target": 999, "leverage": 100},
    )
    assert response.status_code == 422


def test_emergency_stop_requires_separate_emergency_role():
    http = api()
    assert http.post("/api/v1/live/emergency-stop", headers={"x-live-operator-token": "operator"}).status_code == 403
