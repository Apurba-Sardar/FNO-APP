from collections import Counter, defaultdict
from statistics import mean

from app.backtesting.metrics import metric_set

from .models import PaperState


def performance(state: PaperState) -> dict:
    trades = state.trades
    base = metric_set(trades).model_dump()
    durations = [item.duration_minutes for item in trades]
    return {
        **base,
        "initial_equity": state.account.initial_equity,
        "current_equity": state.account.equity,
        "total_return_percent": (
            state.account.equity / state.account.initial_equity - 1
        ) * 100,
        "average_win": mean([item.net_pnl for item in trades if item.net_pnl > 0])
        if any(item.net_pnl > 0 for item in trades) else 0,
        "average_loss": mean([item.net_pnl for item in trades if item.net_pnl < 0])
        if any(item.net_pnl < 0 for item in trades) else 0,
        "average_duration_minutes": mean(durations) if durations else 0,
        "total_fees": sum(item.fees for item in trades),
        "total_slippage": sum(item.slippage for item in trades),
        "average_mfe": mean([item.maximum_favorable_excursion for item in trades]) if trades else 0,
        "average_mae": mean([item.maximum_adverse_excursion for item in trades]) if trades else 0,
        "open_positions": sum(item.status.value == "open" for item in state.positions),
        "strategy_breakdown": _groups(trades, "strategy"),
        "direction_breakdown": _groups(trades, "direction"),
        "r_distribution": dict(Counter(_r_bucket(item.r_multiple) for item in trades)),
    }


def _groups(trades, field: str) -> dict:
    groups = defaultdict(list)
    for trade in trades:
        value = getattr(trade, field)
        groups[getattr(value, "value", value)].append(trade)
    return {key: metric_set(items).model_dump() for key, items in groups.items()}


def _r_bucket(value: float) -> str:
    if value <= -1:
        return "<=-1R"
    if value <= 0:
        return "-1R-0R"
    if value <= 1:
        return "0R-1R"
    if value <= 2:
        return "1R-2R"
    return ">2R"


def equity_curve(state: PaperState) -> list[dict]:
    equity = state.account.initial_equity
    peak = equity
    points = []
    for trade in sorted(state.trades, key=lambda item: item.timestamp):
        equity += trade.net_pnl
        peak = max(peak, equity)
        points.append({
            "timestamp": trade.timestamp,
            "equity": equity,
            "drawdown": peak - equity,
            "cumulative_pnl": equity - state.account.initial_equity,
        })
    if not points:
        points.append({
            "timestamp": state.account.updated_at,
            "equity": state.account.equity,
            "drawdown": state.account.drawdown,
            "cumulative_pnl": state.account.equity - state.account.initial_equity,
        })
    return points


def compare_metrics(paper: dict, backtest) -> dict:
    if backtest is None or backtest.performance is None:
        return {"available": False, "reason": "backtest baseline unavailable", "deviations": {}}
    bt = backtest.performance
    fields = {
        "trade_count": (paper["trades"], bt.trades),
        "win_rate": (paper["win_rate"], bt.win_rate),
        "profit_factor": (paper["profit_factor"], bt.profit_factor),
        "expectancy": (paper["expectancy"], bt.expectancy),
        "average_r": (paper["average_r"], bt.average_r),
        "max_drawdown": (paper["maximum_drawdown"], bt.maximum_drawdown),
        "average_duration": (paper["average_duration_minutes"], backtest.execution_metrics.average_trade_duration_minutes if backtest.execution_metrics else 0),
        "fees": (paper["total_fees"], backtest.execution_metrics.total_fees if backtest.execution_metrics else 0),
        "slippage": (paper["total_slippage"], backtest.execution_metrics.total_slippage if backtest.execution_metrics else 0),
    }
    return {
        "available": True,
        "paper": {key: value[0] for key, value in fields.items()},
        "backtest": {key: value[1] for key, value in fields.items()},
        "deviations": {
            key: None if values[0] is None or values[1] is None else values[0] - values[1]
            for key, values in fields.items()
        },
    }
