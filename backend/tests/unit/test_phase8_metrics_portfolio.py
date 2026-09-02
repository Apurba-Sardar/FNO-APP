from datetime import timedelta
from uuid import uuid4

from app.backtesting.execution import ExitFill, SimulatedExecutionEngine
from app.backtesting.metrics import metric_set, performance
from app.backtesting.models import ExitReason
from app.backtesting.portfolio import BacktestPortfolio
from tests.phase7_fixtures import decision, setup
from tests.phase8_fixtures import NOW, candle, config


def closed_trade(exit_price=102):
    engine = SimulatedExecutionEngine(config())
    position = engine.enter(setup(evaluation_timestamp=NOW), decision(), candle(), uuid4(), {}, "normal")
    return engine.close(position, ExitFill(ExitReason.TAKE_PROFIT, exit_price), NOW + timedelta(minutes=5))


def test_portfolio_records_one_entry_one_exit_and_equity_event():
    portfolio = BacktestPortfolio(100_000)
    position = closed_trade()
    assert portfolio.add(position)
    assert not portfolio.add(position)
    trade = portfolio.record_close(uuid4(), position, "test-v1")
    point = portfolio.mark(NOW + timedelta(minutes=5))
    assert trade.entry_time < trade.exit_time
    assert point.equity == portfolio.account_equity
    assert len(portfolio.trades) == 1


def test_metrics_known_win_and_loss_distribution():
    win = closed_trade(102)
    loss = closed_trade(98)
    portfolio = BacktestPortfolio(100_000)
    for item in (win, loss):
        portfolio.add(item)
        portfolio.record_close(uuid4(), item, "test-v1")
        portfolio.mark(item.exit_timestamp)
    metrics = metric_set(portfolio.trades)
    summary = performance(100_000, portfolio.equity, portfolio.trades, portfolio.equity_curve, NOW, NOW + timedelta(days=1))
    assert metrics.trades == 2
    assert metrics.wins == 1 and metrics.losses == 1
    assert summary.maximum_consecutive_losses == 1
    assert summary.maximum_drawdown >= 0
