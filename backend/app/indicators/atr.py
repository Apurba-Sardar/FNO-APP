from app.market_data.models import NormalizedCandle

from .exceptions import IndicatorError


def true_ranges(candles: list[NormalizedCandle]) -> list[float]:
    if not candles:
        return []
    ranges = [candles[0].high - candles[0].low]
    for current, previous in zip(candles[1:], candles):
        if current.high < current.low:
            raise IndicatorError("candle high cannot be lower than low")
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return ranges


def atr(candles: list[NormalizedCandle], period: int = 14) -> list[float | None]:
    if period <= 1:
        raise IndicatorError("ATR period must be greater than one")
    ranges = true_ranges(candles)
    output: list[float | None] = [None] * len(ranges)
    if len(ranges) < period:
        return output
    current = sum(ranges[:period]) / period
    output[period - 1] = current
    for index in range(period, len(ranges)):
        current = (current * (period - 1) + ranges[index]) / period
        output[index] = current
    return output
