from app.indicators.models import PriceLevel

from .config import StrategyConfig
from .models import StrategyDirection


def stop_from_structure(
    direction: StrategyDirection,
    entry: float,
    atr: float,
    supports: list[PriceLevel],
    resistances: list[PriceLevel],
    config: StrategyConfig,
) -> float | None:
    if atr <= 0:
        return None
    if direction == StrategyDirection.LONG:
        candidates = [level.price for level in supports if level.price < entry]
        anchor = max(candidates) if candidates else entry - atr
        stop = anchor - atr * config.stop_atr_buffer
    else:
        candidates = [level.price for level in resistances if level.price > entry]
        anchor = min(candidates) if candidates else entry + atr
        stop = anchor + atr * config.stop_atr_buffer
    distance = abs(entry - stop)
    if not config.minimum_stop_distance_atr * atr <= distance <= config.maximum_stop_distance_atr * atr:
        return None
    return stop


def target_and_rr(
    direction: StrategyDirection,
    entry: float,
    stop: float,
    supports: list[PriceLevel],
    resistances: list[PriceLevel],
    config: StrategyConfig,
) -> tuple[float, float]:
    risk = abs(entry - stop)
    preferred = entry + risk * config.preferred_risk_reward if direction == StrategyDirection.LONG else entry - risk * config.preferred_risk_reward
    if direction == StrategyDirection.LONG:
        barriers = sorted(level.price for level in resistances if level.price > entry)
        target = min(preferred, barriers[0]) if barriers else preferred
        reward = target - entry
    else:
        barriers = sorted((level.price for level in supports if level.price < entry), reverse=True)
        target = max(preferred, barriers[0]) if barriers else preferred
        reward = entry - target
    return target, max(0.0, reward / risk) if risk else 0.0
