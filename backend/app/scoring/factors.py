from collections.abc import Iterable
from math import isfinite

from app.domain.market import Timeframe
from app.indicators.models import TimeframeAnalysis, TrendState
from app.scanner.models import (
    LiquidityClassification,
    ScannerCandidate,
    VolatilitySuitability,
    VolumeActivity,
)

from .config import ScoringConfig
from .models import (
    FactorName,
    FactorStatus,
    OpportunityDirection,
    ScoreFactor,
)


def clamp(value: float) -> float:
    if not isfinite(value):
        raise ValueError("factor values must be finite")
    return max(0.0, min(100.0, value))


def status_for(score: float, available: bool = True) -> FactorStatus:
    if not available:
        return FactorStatus.UNAVAILABLE
    if score >= 65:
        return FactorStatus.POSITIVE
    if score < 40:
        return FactorStatus.NEGATIVE
    return FactorStatus.NEUTRAL


def make_factor(
    name: FactorName,
    score: float,
    weight: float,
    raw: dict,
    explanation: str,
    warnings: list[str] | None = None,
    *,
    available: bool = True,
) -> ScoreFactor:
    score = clamp(score)
    return ScoreFactor(
        factor_name=name,
        raw_value=raw,
        normalized_score=score,
        weight=weight,
        weighted_contribution=score * weight / 100,
        status=status_for(score, available),
        explanation=explanation,
        warnings=warnings or [],
    )


def _target(direction: OpportunityDirection) -> str:
    return "bullish" if direction == OpportunityDirection.BULLISH else "bearish"


def _state_score(state: str | None, direction: OpportunityDirection) -> float:
    if state is None:
        return 50
    state = state.lower()
    target = _target(direction)
    opposite = "bearish" if target == "bullish" else "bullish"
    if target in state or (target == "bullish" and "positive" in state):
        return 100
    if opposite in state or (target == "bearish" and "positive" in state):
        return 0
    if target == "bullish" and "negative" in state:
        return 0
    if target == "bearish" and "negative" in state:
        return 100
    return 50


def _boolean_score(value: bool | None, direction: OpportunityDirection) -> float:
    if value is None:
        return 50
    bullish = 100 if value else 0
    return bullish if direction == OpportunityDirection.BULLISH else 100 - bullish


def _average(values: Iterable[float]) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0


def trend_factor(
    analysis: TimeframeAnalysis | None,
    direction: OpportunityDirection,
    name: FactorName,
    weight: float,
    context_trend: TrendState | None = None,
) -> ScoreFactor:
    if analysis is None or not analysis.data_quality.sufficient_data:
        return make_factor(
            name,
            0,
            weight,
            {"available": False},
            "Required timeframe analysis is unavailable.",
            ["missing_or_insufficient_timeframe"],
            available=False,
        )
    target = _target(direction)
    trend = analysis.trend.value
    trend_score = 50.0
    if trend == target:
        trend_score = 50 + analysis.trend_strength / 2
    elif trend in {"bullish", "bearish"}:
        trend_score = 50 - analysis.trend_strength / 2
    elif trend == "transition":
        trend_score = 40
    momentum = analysis.momentum
    indicators = analysis.indicators
    structure = analysis.structure
    structure_score = _average(
        [
            _boolean_score(structure.higher_high, direction),
            _boolean_score(structure.higher_low, direction),
            _boolean_score(not structure.lower_high, direction),
            _boolean_score(not structure.lower_low, direction),
        ]
    )
    ema_score = _state_score(momentum.ema_alignment if momentum else None, direction)
    price_score = (
        _average(
            [
                _boolean_score(indicators.price_above_ema20, direction),
                _boolean_score(indicators.price_above_ema50, direction),
                _boolean_score(indicators.price_above_ema200, direction),
            ]
        )
        if indicators
        else 50
    )
    score = trend_score * 0.4 + structure_score * 0.25 + ema_score * 0.2 + price_score * 0.15
    warnings = []
    if context_trend in {TrendState.BULLISH, TrendState.BEARISH}:
        if analysis.trend == context_trend:
            score += 5
        elif analysis.trend in {TrendState.BULLISH, TrendState.BEARISH}:
            score -= 15
            warnings.append("higher_timeframe_conflict")
    return make_factor(
        name,
        score,
        weight,
        {
            "trend": trend,
            "trend_strength": analysis.trend_strength,
            "structure": structure.trend.value,
            "ema_alignment": momentum.ema_alignment if momentum else None,
            "price_above_ema20": indicators.price_above_ema20 if indicators else None,
            "price_above_ema50": indicators.price_above_ema50 if indicators else None,
            "price_above_ema200": indicators.price_above_ema200 if indicators else None,
        },
        f"{analysis.timeframe.value} evidence is {trend} with {analysis.trend_strength:.2f}/100 trend strength for the {target} case.",
        warnings,
    )


def momentum_factor(
    analysis: TimeframeAnalysis | None,
    direction: OpportunityDirection,
    weight: float,
) -> ScoreFactor:
    if analysis is None or analysis.momentum is None:
        return make_factor(
            FactorName.ONE_HOUR_MOMENTUM,
            0,
            weight,
            {"available": False},
            "1h momentum data is unavailable.",
            ["missing_momentum"],
            available=False,
        )
    momentum = analysis.momentum
    target_positive = direction == OpportunityDirection.BULLISH
    roc_scores = []
    for value in (momentum.roc_5, momentum.roc_10):
        if value is not None:
            aligned = value >= 0 if target_positive else value <= 0
            roc_scores.append(75 if aligned else 25)
    range_score = 50
    if analysis.volatility and analysis.volatility.recent_range_expansion is not None:
        expansion = analysis.volatility.recent_range_expansion
        range_score = 75 if 0.8 <= expansion <= 2 else 40 if expansion > 3 else 50
    score = _average(
        [
            _state_score(momentum.rsi_state, direction),
            _state_score(momentum.macd_state, direction),
            _state_score(momentum.price_momentum, direction),
            _state_score(momentum.ema_alignment, direction),
            _average(roc_scores) if roc_scores else 50,
            range_score,
        ]
    )
    return make_factor(
        FactorName.ONE_HOUR_MOMENTUM,
        score,
        weight,
        momentum.model_dump(mode="json"),
        f"1h momentum evidence is evaluated in the {_target(direction)} context; RSI is treated as state, not a reversal instruction.",
    )


def setup_factor(
    analysis: TimeframeAnalysis | None,
    direction: OpportunityDirection,
    weight: float,
) -> ScoreFactor:
    if analysis is None or analysis.indicators is None or analysis.momentum is None:
        return make_factor(
            FactorName.FIFTEEN_MINUTE_SETUP,
            0,
            weight,
            {"available": False},
            "15m setup data is unavailable.",
            ["missing_setup_data"],
            available=False,
        )
    indicators = analysis.indicators
    momentum = analysis.momentum
    structure = analysis.structure
    score = _average(
        [
            _state_score(analysis.trend.value, direction),
            _state_score(structure.trend.value, direction),
            _state_score(momentum.price_momentum, direction),
            _state_score(momentum.ema_alignment, direction),
            _boolean_score(indicators.price_above_vwap, direction),
            _boolean_score(indicators.price_above_ema20, direction),
            80 if indicators.relative_volume and indicators.relative_volume >= 1.5 else 55,
            80
            if (direction == OpportunityDirection.BULLISH and structure.higher_low)
            or (direction == OpportunityDirection.BEARISH and structure.lower_high)
            else 40,
        ]
    )
    return make_factor(
        FactorName.FIFTEEN_MINUTE_SETUP,
        score,
        weight,
        {
            "trend": analysis.trend.value,
            "structure": structure.trend.value,
            "ema_alignment": momentum.ema_alignment,
            "price_momentum": momentum.price_momentum,
            "price_above_vwap": indicators.price_above_vwap,
            "relative_volume": indicators.relative_volume,
        },
        f"15m structure, VWAP, EMA, momentum, and volume provide a {score:.2f}/100 technical-quality reading for the {_target(direction)} case.",
    )


def volume_factor(
    candidate: ScannerCandidate,
    direction: OpportunityDirection,
    weight: float,
) -> ScoreFactor:
    activity_scores = {
        VolumeActivity.QUIET: 20,
        VolumeActivity.NORMAL: 55,
        VolumeActivity.ACTIVE: 80,
        VolumeActivity.HIGH_ACTIVITY: 85,
        VolumeActivity.EXTREME: 55,
    }
    score = float(activity_scores[candidate.volume.activity])
    if candidate.volume.trend == "increasing":
        score += 5
    change = candidate.market.price_change_percent_24h
    if change is not None and change != 0:
        aligned = change > 0 if direction == OpportunityDirection.BULLISH else change < 0
        score += 5 if aligned else -5
    warnings = ["extreme_volume_requires_context"] if candidate.volume.activity == "extreme" else []
    return make_factor(
        FactorName.VOLUME_EXPANSION,
        score,
        weight,
        candidate.volume.model_dump(mode="json"),
        f"Relative-volume activity is {candidate.volume.activity.value}; extreme volume is deliberately not awarded a maximum score.",
        warnings,
    )


def liquidity_factor(candidate: ScannerCandidate, weight: float) -> ScoreFactor:
    class_scores = {
        LiquidityClassification.EXCELLENT: 95,
        LiquidityClassification.GOOD: 85,
        LiquidityClassification.ACCEPTABLE: 65,
        LiquidityClassification.POOR: 25,
        LiquidityClassification.UNUSABLE: 0,
    }
    score = float(class_scores[candidate.liquidity.classification])
    if candidate.liquidity.spread_percent is not None:
        score -= min(candidate.liquidity.spread_percent / 0.25 * 20, 20)
    if candidate.liquidity.estimated_slippage_percent is not None:
        score -= min(candidate.liquidity.estimated_slippage_percent / 0.35 * 20, 20)
    return make_factor(
        FactorName.LIQUIDITY_ORDER_BOOK,
        score,
        weight,
        candidate.liquidity.model_dump(mode="json"),
        f"Order-book liquidity is {candidate.liquidity.classification.value}, including measured spread, depth, and estimated slippage.",
    )


def volatility_factor(candidate: ScannerCandidate, weight: float) -> ScoreFactor:
    scores = {
        VolatilitySuitability.TOO_LOW: 20,
        VolatilitySuitability.SUITABLE: 95,
        VolatilitySuitability.HIGH: 70,
        VolatilitySuitability.EXTREME: 10,
        VolatilitySuitability.UNKNOWN: 0,
    }
    return make_factor(
        FactorName.VOLATILITY_ATR,
        scores[candidate.volatility.suitability],
        weight,
        candidate.volatility.model_dump(mode="json"),
        f"ATR conditions are classified {candidate.volatility.suitability.value}; movement is rewarded only when usable for analysis.",
        ["extreme_volatility"]
        if candidate.volatility.suitability == VolatilitySuitability.EXTREME
        else [],
    )


def structural_rr(
    candidate: ScannerCandidate,
    direction: OpportunityDirection,
    config: ScoringConfig,
) -> tuple[float | None, dict]:
    analysis = candidate.timeframes.get(Timeframe.MINUTE_15)
    entry = candidate.market.last_price
    atr = candidate.volatility.atr
    if analysis is None or entry is None or atr is None or atr <= 0:
        return None, {"available": False}
    supports = sorted(
        (level for level in analysis.structure.support_levels if level.price < entry),
        key=lambda level: entry - level.price,
    )
    resistances = sorted(
        (level for level in analysis.structure.resistance_levels if level.price > entry),
        key=lambda level: level.price - entry,
    )
    if not supports or not resistances:
        return None, {"available": False, "reason": "two_sided_structure_missing"}
    support = supports[0]
    resistance = resistances[0]
    if direction == OpportunityDirection.BULLISH:
        structural_risk = entry - support.price
        reward = resistance.price - entry
        stop_source, target_source = support, resistance
    else:
        structural_risk = resistance.price - entry
        reward = entry - support.price
        stop_source, target_source = resistance, support
    risk = max(structural_risk, atr * config.hypothetical_atr_stop_multiple)
    minimum_risk = atr * 0.25
    if risk <= minimum_risk or reward <= 0:
        return None, {"available": False, "reason": "invalid_structural_room"}
    rr = reward / risk
    return rr, {
        "entry": entry,
        "atr": atr,
        "hypothetical_atr_stop_multiple": config.hypothetical_atr_stop_multiple,
        "risk_distance": risk,
        "structural_risk_distance": structural_risk,
        "reward_distance": reward,
        "stop_level_type": stop_source.type.value,
        "target_level_type": target_source.type.value,
        "stop_level_strength": stop_source.strength,
        "target_level_strength": target_source.strength,
    }


def support_resistance_factor(
    candidate: ScannerCandidate,
    direction: OpportunityDirection,
    weight: float,
    config: ScoringConfig,
) -> tuple[ScoreFactor, float | None, dict]:
    rr, raw = structural_rr(candidate, direction, config)
    if rr is None:
        return (
            make_factor(
                FactorName.SUPPORT_RESISTANCE,
                35,
                weight,
                raw,
                "Nearby two-sided potential support/resistance is incomplete.",
                ["structural_room_unavailable"],
                available=False,
            ),
            None,
            raw,
        )
    reward = raw["reward_distance"]
    atr = raw["atr"]
    room_multiple = reward / atr
    score = (
        25
        if room_multiple < 0.25
        else 45
        if room_multiple < 0.75
        else 70
        if room_multiple < 1.5
        else 90
    )
    warning = "nearby_opposing_level" if room_multiple < config.nearby_level_atr_multiple else None
    return (
        make_factor(
            FactorName.SUPPORT_RESISTANCE,
            score,
            weight,
            {**raw, "room_atr_multiple": room_multiple},
            f"Potential opposing structure leaves {room_multiple:.2f} ATR of directional room; levels are zones, not guarantees.",
            [warning] if warning else [],
        ),
        rr,
        raw,
    )


def risk_reward_factor(
    rr: float | None, raw: dict, weight: float, config: ScoringConfig
) -> ScoreFactor:
    if rr is None:
        return make_factor(
            FactorName.RISK_REWARD,
            0,
            weight,
            raw,
            "Estimated structural R:R is unavailable because two-sided structure is insufficient.",
            ["estimated_structural_rr_unavailable"],
            available=False,
        )
    score = rr / config.rr_full_score * 100
    return make_factor(
        FactorName.RISK_REWARD,
        score,
        weight,
        {**raw, "estimated_structural_rr": rr},
        f"Estimated structural R:R is {rr:.2f}; this is analytical room, not an executable stop or target.",
        ["limited_structural_rr"] if rr < 1 else [],
    )
