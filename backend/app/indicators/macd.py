from dataclasses import dataclass

from .ema import ema, ema_from_optional
from .exceptions import IndicatorError


@dataclass(frozen=True)
class MacdSeries:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> MacdSeries:
    if not 1 < fast < slow or signal <= 1:
        raise IndicatorError("MACD requires 1 < fast < slow and signal > 1")
    fast_values, slow_values = ema(values, fast), ema(values, slow)
    line = [
        None if fast_value is None or slow_value is None else fast_value - slow_value
        for fast_value, slow_value in zip(fast_values, slow_values, strict=True)
    ]
    signal_values = ema_from_optional(line, signal)
    histogram = [
        None if value is None or signal_value is None else value - signal_value
        for value, signal_value in zip(line, signal_values, strict=True)
    ]
    return MacdSeries(line, signal_values, histogram)


def crossover(series: MacdSeries) -> tuple[bool, bool]:
    valid = [
        (value, signal)
        for value, signal in zip(series.macd, series.signal, strict=True)
        if value is not None and signal is not None
    ]
    if len(valid) < 2:
        return False, False
    previous, current = valid[-2], valid[-1]
    bullish = previous[0] <= previous[1] and current[0] > current[1]
    bearish = previous[0] >= previous[1] and current[0] < current[1]
    return bullish, bearish
