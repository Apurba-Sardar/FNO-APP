from app.strategy.models import StrategyDirection


def valid_stop(direction: StrategyDirection, entry: float, stop: float) -> bool:
    return (direction == StrategyDirection.LONG and stop < entry) or (
        direction == StrategyDirection.SHORT and stop > entry
    )


def valid_target(direction: StrategyDirection, entry: float, target: float) -> bool:
    return (direction == StrategyDirection.LONG and target > entry) or (
        direction == StrategyDirection.SHORT and target < entry
    )


def structural_rr(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    return abs(target - entry) / risk if risk > 0 else 0.0

