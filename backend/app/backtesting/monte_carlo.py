import random
from statistics import quantiles


def trade_order_monte_carlo(outcomes: list[float], initial_equity: float, runs=1000, seed=42):
    if not outcomes or runs <= 0:
        return {"runs": 0, "warning": "No trades available for trade-order simulation."}
    generator = random.Random(seed)
    final_equities = []
    drawdowns = []
    for _ in range(runs):
        sample = outcomes.copy()
        generator.shuffle(sample)
        equity = peak = initial_equity
        maximum_drawdown = 0.0
        for outcome in sample:
            equity += outcome
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, peak - equity)
        final_equities.append(equity)
        drawdowns.append(maximum_drawdown)
    final_percentiles = quantiles(final_equities, n=100, method="inclusive")
    drawdown_percentiles = quantiles(drawdowns, n=100, method="inclusive")
    return {
        "runs": runs,
        "seed": seed,
        "final_equity_p05": final_percentiles[4],
        "final_equity_p50": final_percentiles[49],
        "final_equity_p95": final_percentiles[94],
        "drawdown_p50": drawdown_percentiles[49],
        "drawdown_p95": drawdown_percentiles[94],
        "warning": "Trade-order uncertainty simulation; not a future prediction.",
    }
