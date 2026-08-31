from app.domain.analysis import Direction, ScoreInputs
from app.domain.market import Candle, Timeframe
from app.indicators import IndicatorEngine, IndicatorSnapshot


class MultiTimeframeAnalyzer:
    def __init__(self, indicators: IndicatorEngine, volume_lookback: int = 20) -> None:
        self.indicators = indicators
        self.volume_lookback = volume_lookback

    @staticmethod
    def trend(snapshot: IndicatorSnapshot, price: float) -> float:
        values = [snapshot.ema20, snapshot.ema50, snapshot.ema200]
        if any(value is None for value in values):
            return 0
        bullish = price > values[0] > values[1] > values[2]
        bearish = price < values[0] < values[1] < values[2]
        return (
            1.0
            if bullish or bearish
            else 0.5
            if (price > values[0] > values[1] or price < values[0] < values[1])
            else 0
        )

    def analyze(
        self, frames: dict[Timeframe, list[Candle]], liquidity_score: float, risk_reward: float
    ) -> tuple[Direction, ScoreInputs, dict[Timeframe, IndicatorSnapshot]]:
        snapshots = {
            tf: self.indicators.snapshot(rows, self.volume_lookback) for tf, rows in frames.items()
        }
        prices = {tf: rows[-1].close for tf, rows in frames.items()}
        daily = snapshots[Timeframe.DAY_1]
        price = prices[Timeframe.DAY_1]
        if daily.ema20 and daily.ema50 and price > daily.ema20 > daily.ema50:
            direction = Direction.LONG
        elif daily.ema20 and daily.ema50 and price < daily.ema20 < daily.ema50:
            direction = Direction.SHORT
        else:
            direction = Direction.NEUTRAL
        h1 = snapshots[Timeframe.HOUR_1]
        m15 = snapshots[Timeframe.MINUTE_15]
        m5 = snapshots[Timeframe.MINUTE_5]
        momentum = (
            1
            if h1.rsi is not None
            and (
                (direction == Direction.LONG and h1.rsi > 50)
                or (direction == Direction.SHORT and h1.rsi < 50)
            )
            else 0
        )
        setup = (
            1
            if m15.macd_histogram is not None
            and (
                (direction == Direction.LONG and m15.macd_histogram > 0)
                or (direction == Direction.SHORT and m15.macd_histogram < 0)
            )
            else 0
        )
        rel_volume = m5.relative_volume or 0
        atr_pct = (m15.atr or 0) / prices[Timeframe.MINUTE_15]
        sr_distance = (
            min(
                abs(prices[Timeframe.MINUTE_15] - (m15.support or price)),
                abs((m15.resistance or price) - prices[Timeframe.MINUTE_15]),
            )
            / prices[Timeframe.MINUTE_15]
        )
        inputs = ScoreInputs(
            weekly_trend=self.trend(snapshots[Timeframe.WEEK_1], prices[Timeframe.WEEK_1]),
            daily_trend=self.trend(daily, price),
            four_hour_trend=self.trend(snapshots[Timeframe.HOUR_4], prices[Timeframe.HOUR_4]),
            one_hour_momentum=momentum,
            fifteen_minute_setup=setup,
            volume_expansion=min(rel_volume / 2, 1),
            liquidity_order_book=max(0, min(liquidity_score, 1)),
            volatility_atr=1 if 0.005 <= atr_pct <= 0.04 else 0.25,
            support_resistance=max(0, 1 - min(sr_distance / 0.03, 1)),
            risk_reward=min(risk_reward / 2, 1),
        )
        return direction, inputs, snapshots
