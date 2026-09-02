from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from app.domain.market import Candle, Timeframe
from app.market_data.models import NormalizedCandle

from .atr import atr as wilder_atr
from .candle import characterize
from .ema import ema
from .macd import crossover, macd
from .models import (
    IndicatorParameters,
    MomentumAnalysis,
    PriceStructure,
    TimeframeAnalysis,
    TrendState,
    VolatilityAnalysis,
    VolatilityRegime,
)
from .models import (
    IndicatorSnapshot as TechnicalIndicatorSnapshot,
)
from .rsi import rsi
from .structure import analyze_structure
from .validation import validate_candles
from .volume import relative_volume, rolling_average
from .vwap import utc_session_vwap


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Phase 1 compatibility snapshot used only by the legacy scanner."""

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
    """Deterministic Phase 3 engine plus backwards-compatible Phase 1 helpers."""

    ema = staticmethod(ema)
    rsi = staticmethod(rsi)

    @staticmethod
    def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
        """Legacy EMA-smoothed ATR retained for Phase 1 scanner compatibility."""
        if not candles:
            return []
        true_ranges = [candles[0].high - candles[0].low]
        for current, previous in zip(candles[1:], candles):
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        return ema(true_ranges, period)

    @staticmethod
    def vwap(candles: list[Candle]) -> list[float | None]:
        cumulative_volume = 0.0
        cumulative_value = 0.0
        output = []
        for candle in candles:
            cumulative_volume += candle.volume
            cumulative_value += ((candle.high + candle.low + candle.close) / 3) * candle.volume
            output.append(cumulative_value / cumulative_volume if cumulative_volume else None)
        return output

    rolling_average = staticmethod(rolling_average)

    @classmethod
    def snapshot(
        cls, candles: list[Candle], volume_lookback: int = 20, swing_window: int = 5
    ) -> IndicatorSnapshot:
        """Legacy scanner adapter; Phase 3 callers should use ``analyze``."""
        if not candles:
            raise ValueError("at least one candle is required")
        closes = [item.close for item in candles]
        volumes = [item.volume for item in candles]
        ema20, ema50, ema200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
        macd_values = macd(closes)
        volume_average = rolling_average(volumes, volume_lookback)[-1]
        recent = candles[-max(1, swing_window) :]
        swing_high = max(item.high for item in recent)
        swing_low = min(item.low for item in recent)
        line = macd_values.macd[-1]
        signal = macd_values.signal[-1]
        return IndicatorSnapshot(
            ema20=ema20[-1],
            ema50=ema50[-1],
            ema200=ema200[-1],
            rsi=rsi(closes)[-1],
            macd=line,
            macd_signal=signal,
            macd_histogram=None if line is None or signal is None else line - signal,
            atr=cls.atr(candles)[-1],
            vwap=cls.vwap(candles)[-1],
            volume_average=volume_average,
            relative_volume=None if not volume_average else volumes[-1] / volume_average,
            swing_high=swing_high,
            swing_low=swing_low,
            support=swing_low,
            resistance=swing_high,
        )

    def __init__(self, parameters: IndicatorParameters | None = None) -> None:
        self.parameters = parameters or IndicatorParameters()

    def analyze(
        self,
        symbol: str,
        timeframe: Timeframe,
        candles: list[NormalizedCandle],
        *,
        stale: bool = False,
        evaluation_timestamp: datetime | None = None,
    ) -> TimeframeAnalysis:
        parameters = self.parameters
        required = max(*parameters.ema_periods, parameters.minimum_candles)
        quality = validate_candles(
            candles,
            timeframe,
            required_candles=required,
            stale=stale,
            now=evaluation_timestamp,
            gap_tolerance=parameters.gap_tolerance,
        )
        clean = self._ordered_unique(candles)
        structure = analyze_structure(
            clean,
            window=parameters.swing_window,
            tolerance_percent=parameters.level_cluster_tolerance_percent,
            maximum_levels=parameters.maximum_levels,
        )
        if not clean:
            return TimeframeAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=None,
                indicators=None,
                candle=None,
                structure=structure,
                momentum=None,
                volatility=None,
                trend=TrendState.NEUTRAL,
                trend_strength=0,
                data_quality=quality,
            )

        closes = [item.close for item in clean]
        volumes = [item.volume for item in clean]
        ema20_values = ema(closes, parameters.ema_periods[0])
        ema50_values = ema(closes, parameters.ema_periods[1])
        ema200_values = ema(closes, parameters.ema_periods[2])
        rsi_values = rsi(closes, parameters.rsi_period)
        macd_values = macd(
            closes, parameters.macd_fast, parameters.macd_slow, parameters.macd_signal
        )
        bullish_cross, bearish_cross = crossover(macd_values)
        atr_values = wilder_atr(clean, parameters.atr_period)
        vwap_values = utc_session_vwap(clean)
        volume_averages = rolling_average(volumes, parameters.volume_ma_period)
        relative_volumes = relative_volume(volumes, parameters.volume_ma_period)
        latest = clean[-1]
        ema20_value, ema50_value, ema200_value = (
            ema20_values[-1],
            ema50_values[-1],
            ema200_values[-1],
        )
        rsi_value = rsi_values[-1]
        macd_value = macd_values.macd[-1]
        signal_value = macd_values.signal[-1]
        histogram = macd_values.histogram[-1]
        atr_value = atr_values[-1]
        vwap_value = vwap_values[-1]
        relative = relative_volumes[-1]
        atr_percent = atr_value / latest.close * 100 if atr_value is not None else None
        snapshot = TechnicalIndicatorSnapshot(
            timestamp=latest.timestamp,
            close=latest.close,
            ema20=ema20_value,
            ema50=ema50_value,
            ema200=ema200_value,
            ema20_above_ema50=self._compare(ema20_value, ema50_value),
            ema50_above_ema200=self._compare(ema50_value, ema200_value),
            price_above_ema20=self._compare(latest.close, ema20_value),
            price_above_ema50=self._compare(latest.close, ema50_value),
            price_above_ema200=self._compare(latest.close, ema200_value),
            rsi=rsi_value,
            rsi_overbought=None if rsi_value is None else rsi_value >= parameters.rsi_overbought,
            rsi_oversold=None if rsi_value is None else rsi_value <= parameters.rsi_oversold,
            macd=macd_value,
            macd_signal=signal_value,
            macd_histogram=histogram,
            macd_bullish_cross=bullish_cross,
            macd_bearish_cross=bearish_cross,
            atr=atr_value,
            atr_percent=atr_percent,
            vwap=vwap_value,
            price_above_vwap=self._compare(latest.close, vwap_value),
            distance_from_vwap_percent=(
                None if vwap_value is None else (latest.close - vwap_value) / vwap_value * 100
            ),
            volume=latest.volume,
            volume_ma=volume_averages[-1],
            relative_volume=relative,
            volume_increasing=None if len(volumes) < 2 else volumes[-1] > volumes[-2],
            volume_decreasing=None if len(volumes) < 2 else volumes[-1] < volumes[-2],
            volume_elevated=(
                None if relative is None else relative >= parameters.elevated_volume_threshold
            ),
            volume_spike=None
            if relative is None
            else relative >= parameters.volume_spike_threshold,
        )
        momentum = self._momentum(closes, snapshot)
        volatility = self._volatility(clean, atr_value, atr_percent)
        trend, strength = self._trend(snapshot, structure, ema20_values)
        return TimeframeAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=latest.timestamp,
            indicators=snapshot,
            candle=characterize(latest),
            structure=structure,
            momentum=momentum,
            volatility=volatility,
            trend=trend,
            trend_strength=strength,
            data_quality=quality,
        )

    @staticmethod
    def _ordered_unique(candles: list[NormalizedCandle]) -> list[NormalizedCandle]:
        unique = {candle.timestamp: candle for candle in candles}
        return sorted(unique.values(), key=lambda candle: candle.timestamp)

    @staticmethod
    def _compare(left: float | None, right: float | None) -> bool | None:
        return None if left is None or right is None else left > right

    def _momentum(
        self, closes: list[float], snapshot: TechnicalIndicatorSnapshot
    ) -> MomentumAnalysis:
        first_period, second_period = self.parameters.roc_periods
        roc_first = self._roc(closes, first_period)
        roc_second = self._roc(closes, second_period)
        rsi_state = (
            "unavailable"
            if snapshot.rsi is None
            else "overbought"
            if snapshot.rsi_overbought
            else "oversold"
            if snapshot.rsi_oversold
            else "positive"
            if snapshot.rsi > 50
            else "negative"
            if snapshot.rsi < 50
            else "neutral"
        )
        macd_state = (
            "unavailable"
            if snapshot.macd_histogram is None
            else "bullish_cross"
            if snapshot.macd_bullish_cross
            else "bearish_cross"
            if snapshot.macd_bearish_cross
            else "positive"
            if snapshot.macd_histogram > 0
            else "negative"
            if snapshot.macd_histogram < 0
            else "neutral"
        )
        available_roc = [value for value in (roc_first, roc_second) if value is not None]
        price_momentum = (
            "unavailable"
            if not available_roc
            else "positive"
            if all(value > 0 for value in available_roc)
            else "negative"
            if all(value < 0 for value in available_roc)
            else "mixed"
        )
        ema_alignment = (
            "bullish"
            if snapshot.ema20_above_ema50 and snapshot.ema50_above_ema200
            else "bearish"
            if snapshot.ema20_above_ema50 is False and snapshot.ema50_above_ema200 is False
            else "mixed"
            if snapshot.ema20_above_ema50 is not None
            else "unavailable"
        )
        return MomentumAnalysis(
            rsi_state=rsi_state,
            macd_state=macd_state,
            price_momentum=price_momentum,
            ema_alignment=ema_alignment,
            roc_5=roc_first,
            roc_10=roc_second,
        )

    @staticmethod
    def _roc(values: list[float], period: int) -> float | None:
        if len(values) <= period or values[-period - 1] <= 0:
            return None
        return (values[-1] / values[-period - 1] - 1) * 100

    def _volatility(
        self,
        candles: list[NormalizedCandle],
        atr_value: float | None,
        atr_percent: float | None,
    ) -> VolatilityAnalysis:
        ranges = [(item.high - item.low) / item.close * 100 for item in candles]
        recent = fmean(ranges[-5:]) if ranges else None
        baseline = fmean(ranges[-25:-5]) if len(ranges) >= 25 else None
        expansion = None if baseline in (None, 0) else recent / baseline
        regime = None
        if atr_percent is not None:
            regime = (
                VolatilityRegime.EXTREME
                if atr_percent >= self.parameters.extreme_volatility_atr_percent
                else VolatilityRegime.HIGH
                if atr_percent >= self.parameters.high_volatility_atr_percent
                else VolatilityRegime.LOW
                if atr_percent < self.parameters.low_volatility_atr_percent
                else VolatilityRegime.NORMAL
            )
        return VolatilityAnalysis(
            atr=atr_value,
            atr_percent=atr_percent,
            recent_range_expansion=expansion,
            regime=regime,
        )

    @staticmethod
    def _trend(
        snapshot: TechnicalIndicatorSnapshot,
        structure: PriceStructure,
        ema20_values: list[float | None],
    ) -> tuple[TrendState, float]:
        bullish_ema = snapshot.price_above_ema20 is True and snapshot.ema20_above_ema50 is True
        bearish_ema = snapshot.price_above_ema20 is False and snapshot.ema20_above_ema50 is False
        if bullish_ema and structure.trend == TrendState.BULLISH:
            trend = TrendState.BULLISH
        elif bearish_ema and structure.trend == TrendState.BEARISH:
            trend = TrendState.BEARISH
        elif (bullish_ema and structure.trend == TrendState.BEARISH) or (
            bearish_ema and structure.trend == TrendState.BULLISH
        ):
            trend = TrendState.TRANSITION
        else:
            trend = TrendState.NEUTRAL

        evidence: list[int] = []
        for value in (
            snapshot.price_above_ema20,
            snapshot.ema20_above_ema50,
            snapshot.ema50_above_ema200,
        ):
            if value is not None:
                evidence.append(1 if value else -1)
        if structure.trend != TrendState.NEUTRAL:
            evidence.append(1 if structure.trend == TrendState.BULLISH else -1)
        valid_ema20 = [value for value in ema20_values if value is not None]
        if len(valid_ema20) >= 6:
            evidence.append(1 if valid_ema20[-1] > valid_ema20[-6] else -1)
        if snapshot.rsi is not None and snapshot.rsi != 50:
            evidence.append(1 if snapshot.rsi > 50 else -1)
        strength = 0 if not evidence else abs(sum(evidence)) / len(evidence) * 100
        return trend, round(strength, 2)
