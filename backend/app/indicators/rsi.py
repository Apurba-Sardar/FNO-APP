from itertools import pairwise
from math import isfinite
from statistics import fmean

from .exceptions import IndicatorError


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if period <= 1:
        raise IndicatorError("RSI period must be greater than one")
    if any(not isfinite(value) for value in values):
        raise IndicatorError("RSI values must be finite")
    output: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return output
    changes = [current - previous for previous, current in pairwise(values)]
    average_gain = fmean(max(change, 0) for change in changes[:period])
    average_loss = fmean(max(-change, 0) for change in changes[:period])

    def value() -> float:
        if average_gain == 0 and average_loss == 0:
            return 50.0
        if average_loss == 0:
            return 100.0
        return 100 - 100 / (1 + average_gain / average_loss)

    output[period] = value()
    for index in range(period + 1, len(values)):
        change = changes[index - 1]
        average_gain = (average_gain * (period - 1) + max(change, 0)) / period
        average_loss = (average_loss * (period - 1) + max(-change, 0)) / period
        output[index] = value()
    return output
