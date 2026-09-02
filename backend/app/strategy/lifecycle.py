from .models import StrategyDirection, StrategyStatus, SymbolStrategyAnalysis


def apply_lifecycle(
    previous: SymbolStrategyAnalysis | None,
    current: SymbolStrategyAnalysis,
) -> SymbolStrategyAnalysis:
    """Apply terminal state transitions without changing deterministic setup rules."""
    if previous is None:
        return current
    price = current.chart[-1].close if current.chart else None
    for name, result in current.results.items():
        old = previous.results.get(name)
        if old is None or old.status not in {StrategyStatus.WATCH, StrategyStatus.ARMED, StrategyStatus.TRIGGERED}:
            continue
        invalidated = price is not None and old.invalidation_price is not None and (
            (old.direction == StrategyDirection.LONG and price <= old.invalidation_price)
            or (old.direction == StrategyDirection.SHORT and price >= old.invalidation_price)
        )
        if invalidated:
            result.status = StrategyStatus.INVALIDATED
            result.explanations.append("The latest completed close crossed the prior setup invalidation level.")
        elif old.expires_at is not None and current.evaluation_timestamp >= old.expires_at and result.status != StrategyStatus.TRIGGERED:
            result.status = StrategyStatus.EXPIRED
            result.explanations.append("The prior setup validity window expired before confirmation.")
    viable = [result for result in current.results.values() if result.status not in {StrategyStatus.NO_SETUP, StrategyStatus.EXPIRED, StrategyStatus.INVALIDATED}]
    current.best_setup = max(viable, key=lambda item: (item.setup_quality_score, item.risk_reward or 0), default=None)
    return current
