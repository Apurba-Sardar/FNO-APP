from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.backtesting.state import BacktestStateStore
from app.paper_trading.config import PaperTradingConfig
from app.paper_trading.models import EngineStatus, PaperSession
from app.paper_trading.state import InMemoryPaperStateRepository


class WebSocket:
    last_message_at = datetime.now(UTC)

    def health(self):
        return {"status": "connected", "last_message_at": self.last_message_at}


class PaperRuntime:
    def __init__(self):
        self.config = PaperTradingConfig()
        self.repository = InMemoryPaperStateRepository()
        self.state = self.repository.new_state()
        self.market_runtime = SimpleNamespace(websocket=WebSocket())
        self.opportunity_state = SimpleNamespace(opportunities={})
        self.strategy_state = SimpleNamespace(analyses={})
        self.risk_state = SimpleNamespace(analyses={})

    @property
    def current_session(self):
        return next((item for item in reversed(self.state.sessions) if item.end_time is None), None)

    async def start(self):
        session = PaperSession(
            start_time=datetime.now(UTC), initial_equity=self.state.account.equity,
            configuration_snapshot=self.config.model_dump(mode="json"),
            strategy_version="phase6-v1", risk_version="phase7-v1",
        )
        self.state.sessions.append(session)
        self.state.engine_status = EngineStatus.RUNNING
        return session

    async def stop(self):
        self.state.engine_status = EngineStatus.STOPPED

    async def reset(self, confirmation):
        from app.paper_trading.exceptions import PaperExecutionRejected

        if confirmation != "RESET PAPER TRADING":
            raise PaperExecutionRejected("exact reset confirmation is required")

    def analytics(self, _backtest=None):
        return ({"trades": 0, "net_pnl": 0}, {"available": False}, {
            "state": "insufficient_sample", "warnings": ["Insufficient live sample size."]
        })


def api():
    application = FastAPI()
    application.include_router(router)
    application.state.paper_runtime = PaperRuntime()
    application.state.backtest_runtime = SimpleNamespace(store=BacktestStateStore())
    return TestClient(application)


def test_paper_read_api_serializes_normalized_state_and_mode_banner():
    http = api()
    status = http.get("/api/v1/paper/status")
    assert status.status_code == 200
    assert status.json()["mode"] == "paper"
    assert status.json()["real_orders"] is False
    assert http.get("/api/v1/paper/account").json()["initial_equity"] == 100_000
    assert http.get("/api/v1/paper/positions").json()["count"] == 0
    assert http.get("/api/v1/paper/orders").json()["count"] == 0
    assert http.get("/api/v1/paper/trades").json()["count"] == 0
    assert http.get("/api/v1/paper/performance").json()["strategy_health"]["state"] == "insufficient_sample"
    assert http.get("/api/v1/paper/health").json()["market_data_status"] == "connected"
    assert http.get("/api/v1/paper/config").json()["execution_model"] == "slippage_adjusted"


def test_start_stop_and_destructive_reset_confirmation():
    http = api()
    started = http.post("/api/v1/paper/start")
    assert started.status_code == 200
    assert started.json()["real_orders"] is False
    assert http.post("/api/v1/paper/stop").status_code == 200
    assert http.post("/api/v1/paper/reset").status_code == 409
    assert http.post(
        "/api/v1/paper/reset", params={"confirmation": "RESET PAPER TRADING"}
    ).status_code == 200


def test_phase9_paper_mutations_remain_available_after_live_adapter_is_added():
    paths = api().app.openapi()["paths"]
    assert "/api/v1/paper/start" in paths
    forbidden_fragments = ("create-order", "cancel-order", "position/modify")
    assert not [path for path in paths if any(value in path.lower() for value in forbidden_fragments)]
