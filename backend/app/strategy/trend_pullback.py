from datetime import timedelta

from app.domain.market import Timeframe

from .base import DeterministicStrategy
from .exits import stop_from_structure, target_and_rr
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


class TrendPullbackStrategy(DeterministicStrategy):
    name = StrategyName.TREND_PULLBACK

    def evaluate(self, context) -> StrategyResult:
        candidate = context.market
        gates = hard_gates(context, self.config)
        direction = self.direction(context)
        if direction == StrategyDirection.NO_SETUP or not all(item.met for item in gates):
            return self.no_setup(context, gates, ["Hard eligibility or directional context is unavailable."])

        weekly = context.timeframes[Timeframe.WEEK_1]
        daily = context.timeframes[Timeframe.DAY_1]
        four_hour = context.timeframes[Timeframe.HOUR_4]
        hour = context.timeframes[Timeframe.HOUR_1]
        setup = context.timeframes[Timeframe.MINUTE_15]
        trigger_frame = context.timeframes[Timeframe.MINUTE_5]
        indicators = setup.indicators
        trigger_indicators = trigger_frame.indicators
        rows = context.candles[Timeframe.MINUTE_5]
        if not indicators or not trigger_indicators or len(rows) < self.config.trigger_lookback + 1:
            return self.no_setup(context, gates, ["Required 15m/5m indicator context is unavailable."], direction=direction)

        weekly_ok = self.trend_matches(weekly.trend, direction) or (
            self.config.allow_weekly_neutral and weekly.trend.value in {"neutral", "transition"}
        )
        daily_ok = self.trend_matches(daily.trend, direction) or not self.config.require_daily_alignment
        four_ok = self.trend_matches(four_hour.trend, direction) or not self.config.require_four_hour_alignment
        hour_ok = self.trend_matches(hour.trend, direction) or hour.trend.value in {"neutral", "transition"}
        trend_conditions = [
            StrategyCondition(name="weekly_not_opposed", met=weekly_ok, explanation="Weekly trend may align or be neutral, but must not strongly oppose."),
            StrategyCondition(name="daily_trend", met=daily_ok, explanation="Daily trend must match the analytical direction."),
            StrategyCondition(name="four_hour_trend", met=four_ok, explanation="4h trend must match the analytical direction."),
            StrategyCondition(name="one_hour_not_opposed", met=hour_ok, explanation="1h trend may align or transition, but must not oppose."),
        ]
        conditions = [*gates, *trend_conditions]
        if not all(item.met for item in trend_conditions):
            return self.no_setup(context, conditions, ["Higher-timeframe trend alignment is incomplete."], direction=direction)

        atr = indicators.atr
        anchors = [value for value in (indicators.ema20, indicators.vwap) if value is not None]
        if not atr or not anchors or not context.current_price:
            return self.no_setup(context, conditions, ["ATR and EMA/VWAP anchors are required."], direction=direction)
        anchor = sum(anchors) / len(anchors)
        zone = EntryZone(low=anchor - atr * self.config.pullback_zone_atr, high=anchor + atr * self.config.pullback_zone_atr)
        price_in_zone = zone.low <= context.current_price <= zone.high

        current = rows[-1]
        preceding = rows[-self.config.trigger_lookback - 1 : -1]
        if direction == StrategyDirection.LONG:
            trigger_price = max(item.high for item in preceding)
            directional_candle = current.close > current.open
            trigger_confirmed = current.close > trigger_price
            structure_ok = not setup.structure.lower_low
            momentum_ok = (trigger_indicators.rsi or 0) >= 45 and (trigger_indicators.macd_histogram or 0) >= 0
        else:
            trigger_price = min(item.low for item in preceding)
            directional_candle = current.close < current.open
            trigger_confirmed = current.close < trigger_price
            structure_ok = not setup.structure.higher_high
            momentum_ok = (trigger_indicators.rsi or 100) <= 55 and (trigger_indicators.macd_histogram or 0) <= 0
        candle_quality = trigger_frame.candle.body_range_ratio if trigger_frame.candle else None
        volume_ok = (trigger_indicators.relative_volume or 0) >= self.config.trigger_relative_volume
        confirmed = trigger_confirmed and directional_candle and (candle_quality or 0) >= self.config.minimum_body_range_ratio and volume_ok
        conditions.extend(
            [
                StrategyCondition(name="pullback_zone", met=price_in_zone, explanation="Latest completed 5m close is inside the ATR-scaled EMA/VWAP zone."),
                StrategyCondition(name="structure_intact", met=structure_ok, explanation="15m structure has not printed the opposing structural break."),
                StrategyCondition(name="closed_candle_trigger", met=confirmed, explanation="A completed 5m candle must cross structure with body and volume confirmation."),
            ]
        )
        entry = current.close if confirmed else trigger_price
        stop = stop_from_structure(direction, entry, atr, setup.structure.support_levels, setup.structure.resistance_levels, self.config)
        if stop is None:
            return self.no_setup(context, conditions, ["A structure-based stop inside configured ATR bounds is unavailable."], direction=direction)
        target, rr = target_and_rr(direction, entry, stop, setup.structure.support_levels, setup.structure.resistance_levels, self.config)
        rr_ok = rr >= self.config.minimum_risk_reward
        conditions.append(StrategyCondition(name="minimum_risk_reward", met=rr_ok, explanation=f"Structural risk/reward {rr:.2f} must be at least {self.config.minimum_risk_reward:.2f}."))

        trend_score = (weekly.trend_strength + daily.trend_strength + four_hour.trend_strength + hour.trend_strength) / 4
        quality, factors = build_quality(
            self.config,
            candidate,
            trend=trend_score,
            structure=90 if structure_ok else 20,
            location=100 if price_in_zone else 55,
            trigger=100 if confirmed else 55,
            volume=100 if volume_ok else 40,
            momentum=85 if momentum_ok else 35,
            room=min(100, rr / self.config.minimum_risk_reward * 70),
            risk_reward=min(100, rr / self.config.preferred_risk_reward * 100),
        )
        if not rr_ok or quality < self.config.minimum_setup_quality:
            result = self.no_setup(context, conditions, ["Setup does not meet minimum risk/reward or quality."], direction=direction, quality_score=quality)
            result.quality_factors = factors
            return result
        status = StrategyStatus.TRIGGERED if confirmed else StrategyStatus.ARMED if trigger_confirmed else StrategyStatus.WATCH
        return StrategyResult(
            symbol=context.symbol,
            strategy=self.name,
            status=status,
            direction=direction,
            evaluation_timestamp=context.evaluation_timestamp,
            opportunity_score=context.opportunity.opportunity_score,
            setup_quality_score=quality,
            quality=quality_class(quality, self.config),
            entry_method=EntryMethod.CLOSED_CANDLE_CONFIRMATION,
            entry_zone=zone,
            trigger_price=trigger_price,
            hypothetical_entry=entry,
            stop_method=StopMethod.STRUCTURE_ATR_BUFFER,
            hypothetical_stop=stop,
            hypothetical_target=target,
            risk_reward=rr,
            invalidation_price=stop,
            expires_at=context.evaluation_timestamp + timedelta(minutes=self.config.setup_expiry_minutes),
            conditions=conditions,
            quality_factors=factors,
            explanations=["Trend pullback analysis uses aligned higher timeframes and a closed 5m trigger."],
            warnings=context.warnings,
        )
