from datetime import timedelta
from uuid import uuid4

import pytest

from app.paper_trading.analytics import compare_metrics, equity_curve, performance
from app.paper_trading.drift import PerformanceDriftMonitor
from app.paper_trading.models import PaperExitReason, PaperOrderStatus, StrategyHealthState
from app.paper_trading.portfolio import refresh_account
from app.paper_trading.reconciliation import reconcile
from tests.phase9_fixtures import NOW, approved, harness, quote, triggered


@pytest.mark.asyncio
async def test_restart_restores_open_position_without_duplicate():
    _, repository, state, executor = harness()
    executor.execute_entry(state, triggered(), approved(), quote(), NOW, "restart")
    await repository.save(state)
    restored = await repository.load()
    assert len(restored.positions) == 1
    assert len([item for item in restored.orders if item.status == PaperOrderStatus.FILLED]) == 1
    assert reconcile(restored) == []
    await repository.save(restored)
    assert len((await repository.load()).positions) == 1


def test_crash_reconciliation_quarantines_orphaned_fill():
    _, _, state, executor = harness()
    executor.execute_entry(state, triggered(), approved(), quote(), NOW, "crash")
    state.positions.clear()  # crash snapshot between order and position writes
    warnings = reconcile(state)
    assert warnings
    assert state.orders[0].status == PaperOrderStatus.REJECTED


def test_metrics_equity_comparison_and_minimum_sample_warning():
    _, _, state, executor = harness()
    position = executor.execute_entry(state, triggered(), approved(), quote(), NOW, "metrics")
    executor.execute_exit(
        state, position, quote(bid=102, ask=102.1, timestamp=NOW + timedelta(seconds=30)),
        PaperExitReason.TAKE_PROFIT, NOW + timedelta(seconds=30), uuid4(), "s", "r"
    )
    metrics = performance(state)
    assert metrics["trades"] == 1
    assert metrics["total_fees"] > 0
    assert len(equity_curve(state)) == 1
    comparison = compare_metrics(metrics, None)
    health = PerformanceDriftMonitor(30).evaluate(metrics, comparison)
    assert health["state"] == StrategyHealthState.INSUFFICIENT_SAMPLE
    assert "Insufficient" in health["warnings"][0]


def test_phase7_is_upstream_of_paper_runtime_and_no_private_api_imports():
    from pathlib import Path

    root = Path(__file__).parents[2] / "app"
    main = (root / "main.py").read_text(encoding="utf-8")
    assert main.index("risk_runtime.evaluate_all") < main.index("paper_runtime.process_risk_results")
    source = "\n".join(path.read_text(encoding="utf-8") for path in (root / "paper_trading").glob("*.py")).lower()
    for forbidden in ("coindcxtrad", "private_client", "place_order", "futures_order"):
        assert forbidden not in source


def test_utc_day_rollover_resets_daily_pnl_without_resetting_equity():
    _, _, state, _ = harness()
    state.account.trading_day = NOW.date()
    state.account.daily_pnl = -100
    state.account.equity = 99_900
    refresh_account(state, NOW + timedelta(days=1))
    assert state.account.daily_pnl == 0
    assert state.account.starting_day_equity == 99_900
    assert state.account.equity == 100_000  # recomputed from durable realized/open state
