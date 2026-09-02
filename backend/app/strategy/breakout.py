from datetime import timedelta

from app.domain.market import Timeframe

from .base import DeterministicStrategy
from .exits import target_and_rr
from .filters import hard_gates
from .models import (
    EntryMethod,
    EntryZone,
    StopMethod,
    StrategyCondition,
    StrategyDirection,
    StrategyName,
    StrategyResult,
    StrategyStatus,
)
from .quality import build_quality, quality_class


class BreakoutStrategy(DeterministicStrategy):
    name = StrategyName.BREAKOUT

    def evaluate(self, context) -> StrategyResult:
        candidate = context.market
        gates = hard_gates(context, self.config)
        direction = self.direction(context)
        if direction == StrategyDirection.NO_SETUP or not all(item.met for item in gates):
            return self.no_setup(context, gates, ["Hard eligibility or directional context is unavailable."])
        frame = context.timeframes[Timeframe.MINUTE_15]
        indicators = frame.indicators
        rows = context.candles[Timeframe.MINUTE_15]
        needed = max(self.config.minimum_consolidation_candles, self.config.consolidation_lookback)
        if not indicators or not indicators.atr or len(rows) < needed + 1:
            return self.no_setup(context, gates, ["Breakout analysis needs ATR and sufficient closed 15m candles."], direction=direction)

        current = rows[-1]
        breakout_candle = rows[-2] if self.config.retest_required else current
        consolidation = (
            rows[-needed - 2 : -2]
            if self.config.retest_required
            else rows[-needed - 1 : -1]
        )
        range_high = max(item.high for item in consolidation)
        range_low = min(item.low for item in consolidation)
        width_atr = (range_high - range_low) / indicators.atr
        consolidation_ok = width_atr <= self.config.maximum_consolidation_width_atr
        level = range_high if direction == StrategyDirection.LONG else range_low
        distance_atr = abs(breakout_candle.close - level) / indicators.atr
        close_break = breakout_candle.close > level if direction == StrategyDirection.LONG else breakout_candle.close < level
        wick_cross = breakout_candle.high > level if direction == StrategyDirection.LONG else breakout_candle.low < level
        candle_range = breakout_candle.high - breakout_candle.low
        body_ratio = abs(breakout_candle.close - breakout_candle.open) / candle_range if candle_range else 0
        adverse_wick = (
            (breakout_candle.high - max(breakout_candle.open, breakout_candle.close)) / candle_range
            if direction == StrategyDirection.LONG and candle_range
            else (min(breakout_candle.open, breakout_candle.close) - breakout_candle.low) / candle_range
            if candle_range
            else 1
        )
        average_volume = sum(item.volume for item in consolidation) / len(consolidation)
        breakout_relative_volume = breakout_candle.volume / average_volume if average_volume else 0
        volume_ok = breakout_relative_volume >= self.config.breakout_relative_volume
        distance_ok = self.config.minimum_breakout_distance_atr <= distance_atr <= self.config.maximum_breakout_distance_atr
        directional = breakout_candle.close > breakout_candle.open if direction == StrategyDirection.LONG else breakout_candle.close < breakout_candle.open
        retest_ok = not self.config.retest_required or (
            current.low <= level < current.close
            if direction == StrategyDirection.LONG
            else current.high >= level > current.close
        )
        confirmed = close_break and directional and body_ratio >= self.config.minimum_body_range_ratio and adverse_wick <= self.config.maximum_breakout_wick_ratio and volume_ok and distance_ok and retest_ok
        near_level = abs(current.close - level) <= indicators.atr * 0.5
        conditions = [
            *gates,
            StrategyCondition(name="consolidation", met=consolidation_ok, explanation=f"The prior {needed} closed 15m candles form an ATR-bounded range."),
            StrategyCondition(name="close_beyond_level", met=close_break, explanation="The completed 15m candle must close beyond the range boundary; a wick is insufficient."),
            StrategyCondition(name="volume_expansion", met=volume_ok, explanation="Relative volume must confirm expansion."),
            StrategyCondition(name="breakout_distance", met=distance_ok, explanation="The close must clear the level without being excessively extended."),
            StrategyCondition(name="breakout_candle_quality", met=confirmed, explanation="Direction, body, wick, volume, and close-distance tests must all pass."),
            StrategyCondition(name="retest_confirmation", met=retest_ok, explanation="Retest confirmation is enforced only when enabled."),
        ]
        if not consolidation_ok:
            return self.no_setup(context, conditions, ["No deterministic consolidation is present."], direction=direction)

        entry = current.close if confirmed else level
        buffer = indicators.atr * self.config.stop_atr_buffer
        stop = level - buffer if direction == StrategyDirection.LONG else level + buffer
        stop_distance_atr = abs(entry - stop) / indicators.atr
        if not self.config.minimum_stop_distance_atr <= stop_distance_atr <= self.config.maximum_stop_distance_atr:
            return self.no_setup(context, conditions, ["Breakout invalidation stop is outside configured ATR bounds."], direction=direction)
        target, rr = target_and_rr(direction, entry, stop, frame.structure.support_levels, frame.structure.resistance_levels, self.config)
        rr_ok = rr >= self.config.minimum_risk_reward
        conditions.append(StrategyCondition(name="minimum_risk_reward", met=rr_ok, explanation=f"Structural risk/reward {rr:.2f} must be at least {self.config.minimum_risk_reward:.2f}."))
        trend_frame = context.timeframes[Timeframe.HOUR_4]
        momentum_ok = (indicators.macd_histogram or 0) >= 0 if direction == StrategyDirection.LONG else (indicators.macd_histogram or 0) <= 0
        quality, factors = build_quality(
            self.config,
            candidate,
            trend=trend_frame.trend_strength if self.trend_matches(trend_frame.trend, direction) else 45,
            structure=90 if consolidation_ok else 20,
            location=90 if near_level or confirmed else 45,
            trigger=100 if confirmed else 60 if wick_cross else 35,
            volume=100 if volume_ok else 35,
            momentum=80 if momentum_ok else 40,
            room=min(100, rr / self.config.minimum_risk_reward * 70),
            risk_reward=min(100, rr / self.config.preferred_risk_reward * 100),
        )
        if not rr_ok or quality < self.config.minimum_setup_quality:
            result = self.no_setup(context, conditions, ["Setup does not meet minimum risk/reward or quality."], direction=direction, quality_score=quality)
            result.quality_factors = factors
            return result
        status = StrategyStatus.TRIGGERED if confirmed else StrategyStatus.ARMED if near_level or wick_cross else StrategyStatus.WATCH
        zone = EntryZone(low=level - buffer * 0.25, high=level + buffer * 0.25)
        return StrategyResult(
            symbol=context.symbol,
            strategy=self.name,
            status=status,
            direction=direction,
            evaluation_timestamp=context.evaluation_timestamp,
            opportunity_score=context.opportunity.opportunity_score,
            setup_quality_score=quality,
            quality=quality_class(quality, self.config),
            entry_method=EntryMethod.BREAKOUT_CLOSE,
            entry_zone=zone,
            trigger_price=level,
            hypothetical_entry=entry,
            stop_method=StopMethod.BREAKOUT_RECLAIM_ATR_BUFFER,
            hypothetical_stop=stop,
            hypothetical_target=target,
            risk_reward=rr,
            invalidation_price=stop,
            expires_at=context.evaluation_timestamp + timedelta(minutes=self.config.setup_expiry_minutes),
            conditions=conditions,
            quality_factors=factors,
            explanations=["Breakout analysis requires a closed 15m range break; wick-only moves are not triggers."],
            warnings=context.warnings,
        )
