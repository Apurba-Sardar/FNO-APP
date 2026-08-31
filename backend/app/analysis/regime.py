from typing import Protocol

from app.domain.analysis import MarketRegime
from app.indicators import IndicatorSnapshot


class RegimeDetector(Protocol):
    def detect(self, snapshot: IndicatorSnapshot, price: float) -> MarketRegime: ...


class SimpleRegimeDetector:
    def detect(self, snapshot: IndicatorSnapshot, price: float) -> MarketRegime:
        if snapshot.atr and snapshot.atr / price > 0.04:
            return MarketRegime.HIGH_VOLATILITY
        if snapshot.ema20 and snapshot.ema50:
            if price > snapshot.ema20 > snapshot.ema50:
                return MarketRegime.TRENDING_BULLISH
            if price < snapshot.ema20 < snapshot.ema50:
                return MarketRegime.TRENDING_BEARISH
        if snapshot.atr and snapshot.atr / price < 0.005:
            return MarketRegime.LOW_VOLATILITY
        return MarketRegime.RANGING
