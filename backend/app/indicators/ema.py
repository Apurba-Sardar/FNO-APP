from math import isfinite
from statistics import fmean

from .exceptions import IndicatorError


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise IndicatorError("EMA period must be positive")
    if any(not isfinite(value) for value in values):
        raise IndicatorError("EMA values must be finite")
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    current = fmean(values[:period])
    output[period - 1] = current
    alpha = 2 / (period + 1)
    for index in range(period, len(values)):
        current += alpha * (values[index] - current)
        output[index] = current
    return output


def ema_from_optional(values: list[float | None], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    first = next((index for index, value in enumerate(values) if value is not None), None)
    if first is None:
        return output
    calculated = ema([value for value in values[first:] if value is not None], period)
    for index, value in enumerate(calculated, start=first):
        output[index] = value
    return output
