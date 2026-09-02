import time

from app.risk.config import RiskConfig
from app.risk.engine import RiskEngine
from tests.phase7_fixtures import context


def test_risk_benchmark_100_complete_setups(monkeypatch):
    class QuietLogger:
        def info(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("app.risk.engine.structlog.get_logger", lambda: QuietLogger())
    engine = RiskEngine(RiskConfig())
    rows = [context() for _ in range(100)]
    started = time.perf_counter()
    decisions = [engine.evaluate(item) for item in rows]
    duration = time.perf_counter() - started
    print(
        f"phase7 benchmark: 100 full risk evaluations: {duration:.6f}s total, "
        f"{duration / 100 * 1000:.4f}ms/setup"
    )
    assert len(decisions) == 100
    assert all(item.allowed for item in decisions)
    assert duration < 5
