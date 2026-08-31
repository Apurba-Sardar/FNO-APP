from dataclasses import dataclass
from statistics import fmean

from app.domain.market import Candle


@dataclass(frozen=True)
class IndicatorSnapshot:
    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    atr: float | None
    vwap: float | None
    volume_average: float | None
    relative_volume: float | None
    swing_high: float | None
    swing_low: float | None
    support: float | None
    resistance: float | None


class IndicatorEngine:
    """Single reusable source for all indicator calculations."""

    @staticmethod
    def ema(values: list[float], period: int) -> list[float | None]:
        if period <= 0:
            raise ValueError("period must be positive")
        out: list[float | None] = [None] * len(values)
        if len(values) < period:
            return out
        current = fmean(values[:period])
        out[period - 1] = current
        alpha = 2 / (period + 1)
        for index in range(period, len(values)):
            current = values[index] * alpha + current * (1 - alpha)
            out[index] = current
        return out

    @staticmethod
    def rsi(values: list[float], period: int = 14) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        if len(values) <= period:
            return out
        changes = [values[i] - values[i - 1] for i in range(1, len(values))]
        avg_gain = fmean(max(x, 0) for x in changes[:period])
        avg_loss = fmean(max(-x, 0) for x in changes[:period])
        out[period] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        for i in range(period + 1, len(values)):
            change = changes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
            out[i] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        return out

    @staticmethod
    def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
        if not candles:
            return []
        tr = [candles[0].high - candles[0].low]
        for current, previous in zip(candles[1:], candles):
            tr.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        return IndicatorEngine.ema(tr, period)

    @staticmethod
    def vwap(candles: list[Candle]) -> list[float | None]:
        total_volume = 0.0
        total_value = 0.0
        result = []
        for candle in candles:
            total_volume += candle.volume
            total_value += ((candle.high + candle.low + candle.close) / 3) * candle.volume
            result.append(total_value / total_volume if total_volume else None)
        return result

    @staticmethod
    def rolling_average(values: list[float], period: int) -> list[float | None]:
        if period <= 0:
            raise ValueError("period must be positive")
        return [
            None if i + 1 < period else fmean(values[i + 1 - period : i + 1])
            for i in range(len(values))
        ]

    @classmethod
    def snapshot(
        cls, candles: list[Candle], volume_lookback: int = 20, swing_window: int = 5
    ) -> IndicatorSnapshot:
        if not candles:
            raise ValueError("at least one candle is required")
        closes = [x.close for x in candles]
        volumes = [x.volume for x in candles]
        ema20, ema50, ema200 = cls.ema(closes, 20), cls.ema(closes, 50), cls.ema(closes, 200)
        fast, slow = cls.ema(closes, 12), cls.ema(closes, 26)
        macd = [None if a is None or b is None else a - b for a, b in zip(fast, slow)]
        valid_macd = [x for x in macd if x is not None]
        signal_values = cls.ema(valid_macd, 9)
        signal = next((x for x in reversed(signal_values) if x is not None), None)
        macd_last = macd[-1]
        volume_avg = cls.rolling_average(volumes, volume_lookback)[-1]
        recent = candles[-max(1, swing_window) :]
        high = max(x.high for x in recent)
        low = min(x.low for x in recent)
        return IndicatorSnapshot(
            ema20=ema20[-1],
            ema50=ema50[-1],
            ema200=ema200[-1],
            rsi=cls.rsi(closes)[-1],
            macd=macd_last,
            macd_signal=signal,
            macd_histogram=None if macd_last is None or signal is None else macd_last - signal,
            atr=cls.atr(candles)[-1],
            vwap=cls.vwap(candles)[-1],
            volume_average=volume_avg,
            relative_volume=None if not volume_avg else volumes[-1] / volume_avg,
            swing_high=high,
            swing_low=low,
            support=low,
            resistance=high,
        )
