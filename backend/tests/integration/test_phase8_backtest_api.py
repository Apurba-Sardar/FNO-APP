from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.backtesting.state import BacktestStateStore
from tests.phase8_fixtures import NOW, config


class MemoryRuntime:
    def __init__(self):
        self.store = BacktestStateStore()

    async def create(self, configuration):
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.backtesting.models import BacktestResult, BacktestStatus

        result = BacktestResult(
            backtest_id=uuid4(),
            status=BacktestStatus.CREATED,
            configuration=configuration,
            created_at=datetime.now(UTC),
        )
        await self.store.save(result)
        return result


client_runtime = MemoryRuntime()


def api():
    application = FastAPI()
    application.include_router(router)
    application.state.backtest_runtime = client_runtime
    return TestClient(application)


def test_backtest_create_list_detail_config_and_report_routes():
    client_runtime.store.results.clear()
    http = api()
    body = {"configuration": config(end_timestamp=NOW + timedelta(hours=1)).model_dump(mode="json")}
    created = http.post("/api/v1/backtests", json=body)
    assert created.status_code == 200
    identifier = created.json()["backtest_id"]
    assert http.get("/api/v1/backtests").json()["count"] == 1
    assert http.get(f"/api/v1/backtests/{identifier}").status_code == 200
    assert http.get(f"/api/v1/backtests/{identifier}/config").json()["initial_equity"] == 100_000
    report = http.get(f"/api/v1/backtests/{identifier}/report")
    assert report.status_code == 200
    assert "Historical strategy validation" in report.text
    assert http.get("/api/v1/backtests/00000000-0000-0000-0000-000000000000").status_code == 404


def test_no_order_trade_or_execute_route_was_added():
    paths = api().app.openapi()["paths"]
    forbidden = {"/api/v1/order", "/api/v1/trade", "/api/v1/execute"}
    assert forbidden.isdisjoint(paths)
