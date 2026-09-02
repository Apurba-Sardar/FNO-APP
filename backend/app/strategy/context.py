from app.domain.market import Timeframe
from app.indicators.ema import ema
from app.indicators.engine import IndicatorEngine
from app.indicators.vwap import utc_session_vwap
from app.market_data.normalization import TIMEFRAME_DURATION
from app.scanner.models import ScannerCandidate
from app.scoring.models import Opportunity

from .config import StrategyConfig
from .models import ChartPoint, StrategyContext


class StrategyContextBuilder:
    """Builds a point-in-time analytical context using completed candles only."""

    def __init__(self, indicator_engine: IndicatorEngine, config: StrategyConfig) -> None:
        self.indicator_engine = indicator_engine
        self.config = config

    def build(
        self,
        opportunity: Opportunity,
        candidate: ScannerCandidate,
        evaluation_timestamp,
    ) -> StrategyContext:
        warnings: list[str] = []
        snapshot_is_future = candidate.scan_timestamp > evaluation_timestamp
        if snapshot_is_future:
            warnings.append("market snapshot is newer than evaluation timestamp")

        filtered = {}
        analyses = {}
        for timeframe in Timeframe:
            source = candidate.recent_candles.get(timeframe, [])
            closed = sorted(
                (
                    candle
                    for candle in source
                    if candle.timestamp + TIMEFRAME_DURATION[timeframe] <= evaluation_timestamp
                ),
                key=lambda candle: candle.timestamp,
            )
            # De-duplicate defensively without mutating the normalized source list.
            unique = {candle.timestamp: candle for candle in closed}
            rows = list(unique.values())
            filtered[timeframe] = rows
            analyses[timeframe] = self.indicator_engine.analyze(
                candidate.symbol,
                timeframe,
                rows,
                evaluation_timestamp=evaluation_timestamp,
            )
            if not rows:
                warnings.append(f"{timeframe.value}: no completed candles")

        lower = filtered.get(Timeframe.MINUTE_5, [])
        current_price = lower[-1].close if lower else None
        chart = self._chart(lower[-self.config.chart_candle_limit :])
        required = (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1, Timeframe.MINUTE_15, Timeframe.MINUTE_5)
        sufficient = not snapshot_is_future and all(
            analyses[timeframe].indicators is not None
            and analyses[timeframe].data_quality.candle_count >= 50
            for timeframe in required
        )
        if not sufficient:
            warnings.append("insufficient completed analytical history")
        latest = lower[-1].timestamp + TIMEFRAME_DURATION[Timeframe.MINUTE_5] if lower else None
        if latest and (evaluation_timestamp - latest).total_seconds() > self.config.maximum_data_age_minutes * 60:
            warnings.append("latest completed 5m candle is stale")
            sufficient = False
        return StrategyContext(
            symbol=candidate.symbol,
            evaluation_timestamp=evaluation_timestamp,
            opportunity=opportunity,
            market=candidate,
            timeframes=analyses,
            candles=filtered,
            current_price=current_price,
            chart=chart,
            warnings=list(dict.fromkeys(warnings)),
            sufficient_data=sufficient,
        )

    @staticmethod
    def _chart(candles) -> list[ChartPoint]:
        if not candles:
            return []
        closes = [candle.close for candle in candles]
        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        vwap = utc_session_vwap(candles)
        return [
            ChartPoint(
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                ema20=ema20[index],
                ema50=ema50[index],
                vwap=vwap[index],
            )
            for index, candle in enumerate(candles)
        ]
