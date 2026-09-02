from math import isfinite

from .exceptions import IndicatorError


def rolling_average(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise IndicatorError("volume moving-average period must be positive")
    if any(not isfinite(value) or value < 0 for value in values):
        raise IndicatorError("volume values must be finite and non-negative")
    output: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index + 1 >= period:
            output[index] = running / period
    return output


def relative_volume(values: list[float], period: int) -> list[float | None]:
    averages = rolling_average(values, period)
    return [
        None if average is None or average == 0 else value / average
        for value, average in zip(values, averages, strict=True)
    ]
