from dataclasses import dataclass

from app.market_data.models import NormalizedCandle

from .models import LevelType, PriceLevel, PriceStructure, SwingPoint, TrendState


@dataclass(frozen=True)
class SwingCollection:
    highs: list[SwingPoint]
    lows: list[SwingPoint]


def detect_swings(candles: list[NormalizedCandle], window: int = 3) -> SwingCollection:
    if window < 1:
        raise ValueError("swing window must be positive")
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    for index in range(window, len(candles) - window):
        candle = candles[index]
        neighbors = candles[index - window : index] + candles[index + 1 : index + window + 1]
        if all(candle.high > other.high for other in neighbors):
            highs.append(SwingPoint(price=candle.high, timestamp=candle.timestamp))
        if all(candle.low < other.low for other in neighbors):
            lows.append(SwingPoint(price=candle.low, timestamp=candle.timestamp))
    return SwingCollection(highs=highs, lows=lows)


def _cluster_levels(
    points: list[SwingPoint],
    current_price: float,
    level_type: LevelType,
    tolerance_percent: float,
    maximum: int,
) -> list[PriceLevel]:
    clusters: list[list[SwingPoint]] = []
    for point in points:
        matching = next(
            (
                cluster
                for cluster in clusters
                if abs(point.price - sum(item.price for item in cluster) / len(cluster))
                / point.price
                * 100
                <= tolerance_percent
            ),
            None,
        )
        if matching is None:
            clusters.append([point])
        else:
            matching.append(point)
    levels = []
    for cluster in clusters:
        price = sum(point.price for point in cluster) / len(cluster)
        if level_type == LevelType.POTENTIAL_SUPPORT and price > current_price:
            continue
        if level_type == LevelType.POTENTIAL_RESISTANCE and price < current_price:
            continue
        latest = max(cluster, key=lambda point: point.timestamp)
        levels.append(
            PriceLevel(
                price=price,
                type=level_type,
                distance_percent=abs(price - current_price) / current_price * 100,
                strength=len(cluster),
                timestamp=latest.timestamp,
                source="repeated_swing_area" if len(cluster) > 1 else "swing_point",
            )
        )
    return sorted(levels, key=lambda level: (-level.strength, level.distance_percent))[:maximum]


def analyze_structure(
    candles: list[NormalizedCandle],
    *,
    window: int = 3,
    tolerance_percent: float = 0.3,
    maximum_levels: int = 3,
) -> PriceStructure:
    swings = (
        detect_swings(candles, window)
        if len(candles) >= window * 2 + 1
        else SwingCollection([], [])
    )
    higher_high = len(swings.highs) >= 2 and swings.highs[-1].price > swings.highs[-2].price
    lower_high = len(swings.highs) >= 2 and swings.highs[-1].price < swings.highs[-2].price
    higher_low = len(swings.lows) >= 2 and swings.lows[-1].price > swings.lows[-2].price
    lower_low = len(swings.lows) >= 2 and swings.lows[-1].price < swings.lows[-2].price
    trend = (
        TrendState.BULLISH
        if higher_high and higher_low
        else TrendState.BEARISH
        if lower_high and lower_low
        else TrendState.NEUTRAL
    )
    price = candles[-1].close if candles else 1.0
    return PriceStructure(
        trend=trend,
        swing_high=swings.highs[-1] if swings.highs else None,
        swing_low=swings.lows[-1] if swings.lows else None,
        higher_high=higher_high,
        higher_low=higher_low,
        lower_high=lower_high,
        lower_low=lower_low,
        support_levels=_cluster_levels(
            swings.lows,
            price,
            LevelType.POTENTIAL_SUPPORT,
            tolerance_percent,
            maximum_levels,
        ),
        resistance_levels=_cluster_levels(
            swings.highs,
            price,
            LevelType.POTENTIAL_RESISTANCE,
            tolerance_percent,
            maximum_levels,
        ),
    )
