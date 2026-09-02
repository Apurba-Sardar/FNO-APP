from datetime import timedelta
from uuid import uuid4

from app.backtesting.config import ExecutionModel, IntrabarPolicy
from app.backtesting.execution import ExitFill, SimulatedExecutionEngine
from app.backtesting.models import ExitReason
from app.strategy.models import StrategyDirection
from tests.phase7_fixtures import decision, setup
from tests.phase8_fixtures import NOW, candle, config


def entered(engine=None, direction=StrategyDirection.LONG):
    engine = engine or SimulatedExecutionEngine(config())
    strategy_setup = setup(direction, evaluation_timestamp=NOW)
    risk = decision(direction=direction)
    position = engine.enter(strategy_setup, risk, candle(), uuid4(), {}, "normal")
    assert position is not None
    return engine, position


def test_clean_take_profit_and_stop_loss_are_deterministic():
    engine, position = entered()
    assert engine.exit_trigger(position, candle(high=103, low=100), NOW).reason == ExitReason.TAKE_PROFIT
    assert engine.exit_trigger(position, candle(high=100, low=98), NOW).reason == ExitReason.STOP_LOSS


def test_ambiguous_intrabar_assumes_stop_first():
    engine, position = entered()
    fill = engine.exit_trigger(position, candle(high=103, low=98), NOW)
    assert fill.reason == ExitReason.STOP_LOSS


def test_gap_through_stop_uses_worse_open_and_fees_reduce_pnl():
    engine, position = entered()
    fill = engine.exit_trigger(position, candle(open=98, high=99, low=97, close=98), NOW)
    assert fill.theoretical_price == 98
    closed = engine.close(position, fill, NOW + timedelta(minutes=5))
    assert closed.net_pnl < closed.gross_pnl
    assert closed.fees > 0
    assert closed.slippage_cost > 0


def test_time_exit_and_backtest_end_are_explicit():
    engine, position = entered()
    fill = engine.exit_trigger(
        position, candle(high=100.5, low=99.5), NOW + timedelta(minutes=241)
    )
    assert fill.reason == ExitReason.TIME_EXIT
    closed = engine.close(
        position, ExitFill(ExitReason.BACKTEST_END, 100), NOW + timedelta(days=1)
    )
    assert closed.exit_reason == ExitReason.BACKTEST_END
    assert len([event for event in closed.lifecycle if event.state == "closed"]) == 1


def test_entry_gap_beyond_risk_drift_is_not_filled():
    engine = SimulatedExecutionEngine(config(execution_model=ExecutionModel.MARKET))
    position = engine.enter(setup(evaluation_timestamp=NOW), decision(), candle(open=102, high=103, low=101, close=102), uuid4(), {}, "normal")
    assert position is None


def test_target_first_policy_is_available_but_not_default():
    cfg = config(intrabar_policy=IntrabarPolicy.ASSUME_TARGET_FIRST)
    engine, position = entered(SimulatedExecutionEngine(cfg))
    assert engine.exit_trigger(position, candle(high=103, low=98), NOW).reason == ExitReason.TAKE_PROFIT
