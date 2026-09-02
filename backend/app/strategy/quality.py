from app.scanner.models import LiquidityClassification, VolatilitySuitability

from .config import StrategyConfig
from .models import QualityFactor, SetupQuality


def quality_class(score: float, config: StrategyConfig) -> SetupQuality:
    if score >= config.excellent_quality_threshold:
        return SetupQuality.EXCELLENT
    if score >= config.good_quality_threshold:
        return SetupQuality.GOOD
    if score >= config.acceptable_quality_threshold:
        return SetupQuality.ACCEPTABLE
    if score >= config.weak_quality_threshold:
        return SetupQuality.WEAK
    return SetupQuality.INVALID


def build_quality(
    config: StrategyConfig,
    candidate,
    *,
    trend: float,
    structure: float,
    location: float,
    trigger: float,
    volume: float,
    momentum: float,
    room: float,
    risk_reward: float,
) -> tuple[float, list[QualityFactor]]:
    liquidity = {
        LiquidityClassification.EXCELLENT: 100,
        LiquidityClassification.GOOD: 85,
        LiquidityClassification.ACCEPTABLE: 65,
    }.get(candidate.liquidity.classification, 0)
    volatility = {
        VolatilitySuitability.SUITABLE: 90,
        VolatilitySuitability.HIGH: 65,
        VolatilitySuitability.TOO_LOW: 20,
        VolatilitySuitability.EXTREME: 0,
    }.get(candidate.volatility.suitability, 35)
    values = {
        "trend_alignment": trend,
        "structure_quality": structure,
        "entry_location": location,
        "trigger_quality": trigger,
        "volume_confirmation": volume,
        "momentum_confirmation": momentum,
        "liquidity": liquidity,
        "volatility": volatility,
        "target_room": room,
        "risk_reward": risk_reward,
    }
    factors = []
    total = 0.0
    weights = config.quality_weights.model_dump()
    for name, value in values.items():
        bounded = max(0.0, min(100.0, float(value)))
        contribution = bounded * weights[name] / 100
        total += contribution
        factors.append(
            QualityFactor(
                name=name,
                score=round(bounded, 2),
                weight=weights[name],
                contribution=round(contribution, 2),
                explanation=f"Deterministic {name.replace('_', ' ')} evidence score.",
            )
        )
    return round(total, 2), factors
