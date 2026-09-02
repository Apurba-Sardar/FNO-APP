from datetime import timedelta
from uuid import uuid4

import pytest

from app.paper_trading.config import PaperTradingConfig
from app.paper_trading.exceptions import (
    PaperConfigurationError,
    PaperExecutionRejected,
    StaleMarketData,
)
from app.paper_trading.models import PaperExitReason, PaperPositionStatus
from app.strategy.models import StrategyDirection
from tests.phase9_fixtures import NOW, approved, harness, quote, triggered


@pytest.mark.parametrize(
    ("direction", "expected"),
    [(StrategyDirection.LONG, 100.1 * 1.0005), (StrategyDirection.SHORT, 99.9 * 0.9995)],
)
def test_bid_ask_adverse_entry_and_fees(direction, expected):
    _, _, state, executor = harness()
    position = executor.execute_entry(
        state, triggered(direction), approved(direction), quote(), NOW, f"setup-{direction.value}"
    )
    assert position.entry_price == pytest.approx(expected)
    assert state.account.fees > 0
    assert position.slippage > 0
    assert len(state.orders) == 3  # entry plus internal TP and SL
    assert state.account.equity < state.account.initial_equity


def test_live_mode_is_impossible_and_source_has_no_private_client_dependency():
    with pytest.raises(PaperConfigurationError):
        from app.paper_trading.execution import PaperTradeExecutor

        PaperTradeExecutor(PaperTradingConfig(), 0.05, mode="live")
    from pathlib import Path

    source = (Path(__file__).parents[2] / "app" / "paper_trading" / "execution.py").read_text().lower()
    assert "coindcx" not in source
    assert "create_order" not in source
    assert "coindcxtradeexecutor" not in source


def test_risk_rejected_duplicate_stale_and_cooldown_are_blocked():
    config, _, state, executor = harness()
    rejected = approved().model_copy(update={"allowed": False})
    with pytest.raises(PaperExecutionRejected):
        executor.execute_entry(state, triggered(), rejected, quote(), NOW, "rejected")
    with pytest.raises(StaleMarketData):
        executor.execute_entry(
            state, triggered(), approved(), quote(timestamp=NOW - timedelta(seconds=46)), NOW, "stale"
        )
    executor.execute_entry(state, triggered(), approved(), quote(), NOW, "same")
    with pytest.raises(PaperExecutionRejected, match="duplicate"):
        executor.execute_entry(state, triggered(), approved(), quote(), NOW, "same")
    state.positions[0].status = PaperPositionStatus.CLOSED
    state.cooldowns["B-TEST_USDT"] = NOW + timedelta(minutes=config.symbol_cooldown_minutes)
    with pytest.raises(PaperExecutionRejected, match="cooldown"):
        executor.execute_entry(state, triggered(), approved(), quote(), NOW, "new")


@pytest.mark.parametrize(
    ("direction", "exit_quote", "reason"),
    [
        (StrategyDirection.LONG, quote(bid=102.1, ask=102.2), PaperExitReason.TAKE_PROFIT),
        (StrategyDirection.LONG, quote(bid=98.9, ask=99), PaperExitReason.STOP_LOSS),
        (StrategyDirection.SHORT, quote(bid=97.8, ask=97.9), PaperExitReason.TAKE_PROFIT),
        (StrategyDirection.SHORT, quote(bid=101, ask=101.1), PaperExitReason.STOP_LOSS),
    ],
)
def test_long_short_tp_sl_and_accounting(direction, exit_quote, reason):
    _, _, state, executor = harness()
    position = executor.execute_entry(
        state, triggered(direction), approved(direction), quote(), NOW, f"{direction}-exit"
    )
    exit_time = NOW + timedelta(seconds=30)
    exit_quote.timestamp = exit_time
    detected = executor.trigger_reason(position, exit_quote, exit_time, 240)
    assert detected == reason
    trade = executor.execute_exit(
        state, position, exit_quote, detected, exit_time, uuid4(), "s", "r"
    )
    assert trade.fees == pytest.approx(trade.entry_fee + trade.exit_fee)
    assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.fees)
    assert state.account.realized_pnl == pytest.approx(trade.net_pnl)
    assert state.account.equity == pytest.approx(state.account.initial_equity + trade.net_pnl)
    assert position.status == PaperPositionStatus.CLOSED


def test_time_exit_and_unrealized_pnl_are_deterministic():
    _, _, state, executor = harness()
    position = executor.execute_entry(state, triggered(), approved(), quote(), NOW, "time")
    later = NOW + timedelta(minutes=241)
    neutral = quote(bid=100, ask=100.1, timestamp=later)
    assert executor.trigger_reason(position, neutral, later, 240) == PaperExitReason.TIME_EXIT
    assert position.unrealized_pnl == pytest.approx((100 - position.entry_price) * position.quantity)


def test_ambiguous_candle_assumes_stop_first():
    _, _, state, executor = harness()
    position = executor.execute_entry(state, triggered(), approved(), quote(), NOW, "ambiguous")
    assert executor.candle_trigger_reason(position, high=103, low=98) == PaperExitReason.STOP_LOSS
