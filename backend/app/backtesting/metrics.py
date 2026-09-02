from collections import defaultdict
from statistics import mean, median

from .models import ExecutionMetrics, MetricSet, PerformanceMetrics, PeriodMetrics


def streaks(values: list[float]) -> tuple[int, int]:
    losses = wins = maximum_losses = maximum_wins = 0
    for value in values:
        if value > 0:
            wins += 1
            losses = 0
        elif value < 0:
            losses += 1
            wins = 0
        else:
            wins = losses = 0
        maximum_losses = max(maximum_losses, losses)
        maximum_wins = max(maximum_wins, wins)
    return maximum_losses, maximum_wins


def metric_set(trades) -> MetricSet:
    pnls = [item.net_pnl for item in trades]
    gains = sum(value for value in pnls if value > 0)
    losses = abs(sum(value for value in pnls if value < 0))
    cumulative = peak = maximum_drawdown = 0.0
    for value in pnls:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)
    return MetricSet(
        trades=len(trades),
        wins=sum(value > 0 for value in pnls),
        losses=sum(value < 0 for value in pnls),
        win_rate=sum(value > 0 for value in pnls) / len(pnls) * 100 if pnls else 0,
        net_pnl=sum(pnls),
        profit_factor=gains / losses if losses else None,
        expectancy=mean(pnls) if pnls else 0,
        average_r=mean([item.r_multiple for item in trades]) if trades else 0,
        maximum_drawdown=maximum_drawdown,
    )


def performance(initial_equity, final_equity, trades, curve, start, end) -> PerformanceMetrics:
    base = metric_set(trades)
    pnls = [item.net_pnl for item in trades]
    rs = [item.r_multiple for item in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    max_losses, max_wins = streaks(pnls)
    years = (end - start).total_seconds() / (365.25 * 86400)
    total_return = (final_equity / initial_equity - 1) * 100
    annualized = (
        (final_equity / initial_equity) ** (1 / years) * 100 - 100
        if years >= 0.25 and final_equity > 0
        else None
    )
    base_values = base.model_dump()
    base_values["maximum_drawdown"] = max((point.drawdown for point in curve), default=0)
    return PerformanceMetrics(
        **base_values,
        initial_equity=initial_equity,
        final_equity=final_equity,
        total_return_percent=total_return,
        annualized_return_percent=annualized,
        average_trade=mean(pnls) if pnls else 0,
        median_trade=median(pnls) if pnls else 0,
        average_win=mean(wins) if wins else 0,
        average_loss=mean(losses) if losses else 0,
        largest_win=max(wins, default=0),
        largest_loss=min(losses, default=0),
        median_r=median(rs) if rs else 0,
        maximum_drawdown_percent=max((point.drawdown_percent for point in curve), default=0),
        average_drawdown=mean([point.drawdown for point in curve]) if curve else 0,
        maximum_consecutive_losses=max_losses,
        maximum_consecutive_wins=max_wins,
    )


def execution_metrics(trades, funding_included: bool) -> ExecutionMetrics:
    return ExecutionMetrics(
        total_fees=sum(item.fees for item in trades),
        total_slippage=sum(item.slippage for item in trades),
        average_slippage=mean([item.slippage for item in trades]) if trades else 0,
        average_entry_slippage=mean(
            [item.risk_decision.estimated_slippage_cost / 2 for item in trades]
        )
        if trades
        else 0,
        average_exit_slippage=mean([item.slippage / 2 for item in trades]) if trades else 0,
        average_trade_duration_minutes=mean([item.duration_minutes for item in trades])
        if trades
        else 0,
        funding_included=funding_included,
    )


def grouped(trades, key) -> dict[str, MetricSet]:
    groups = defaultdict(list)
    for trade in trades:
        groups[str(key(trade))].append(trade)
    return {name: metric_set(rows) for name, rows in sorted(groups.items())}


def score_bucket(value: float) -> str:
    lower = max(0, min(90, int(value // 10 * 10)))
    return "90-100" if lower >= 90 else f"{lower}-{lower + 9}"


def r_distribution(trades) -> dict[str, int]:
    labels = ["<=-3R", "-3R--2R", "-2R--1R", "-1R-0R", "0R-1R", "1R-2R", "2R-3R", ">3R"]
    result = dict.fromkeys(labels, 0)
    for trade in trades:
        value = trade.r_multiple
        label = (
            "<=-3R" if value <= -3 else "-3R--2R" if value <= -2 else "-2R--1R" if value <= -1
            else "-1R-0R" if value <= 0 else "0R-1R" if value <= 1 else "1R-2R" if value <= 2
            else "2R-3R" if value <= 3 else ">3R"
        )
        result[label] += 1
    return result


def period_metrics(trades, monthly: bool) -> list[PeriodMetrics]:
    groups = defaultdict(list)
    for trade in trades:
        period = trade.exit_time.strftime("%Y-%m" if monthly else "%Y-%m-%d")
        groups[period].append(trade)
    return [
        PeriodMetrics(period=period, **metric_set(rows).model_dump())
        for period, rows in sorted(groups.items())
    ]
