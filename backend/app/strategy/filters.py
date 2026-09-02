from app.domain.market import Timeframe
from app.scanner.models import CandidateStatus, LiquidityClassification

from .config import StrategyConfig
from .models import StrategyCondition, StrategyContext


def hard_gates(context: StrategyContext, config: StrategyConfig) -> list[StrategyCondition]:
    candidate = context.market
    checks = [
        StrategyCondition(
            name="opportunity_eligible",
            met=context.opportunity.eligible and candidate.status in {CandidateStatus.ELIGIBLE, CandidateStatus.WARNING},
            explanation="Phase 4 liquidity filters and Phase 5 hard gates remain authoritative.",
        ),
        StrategyCondition(
            name="opportunity_score",
            met=context.opportunity.opportunity_score >= config.minimum_opportunity_score,
            explanation=f"Opportunity score must be at least {config.minimum_opportunity_score:.1f}.",
        ),
        StrategyCondition(
            name="completed_data",
            met=context.sufficient_data,
            explanation="Required timeframes must contain sufficient, closed, non-stale candles.",
        ),
        StrategyCondition(
            name="spread",
            met=candidate.liquidity.spread_percent is not None
            and candidate.liquidity.spread_percent <= config.maximum_spread_percent,
            explanation=f"Spread must be known and no more than {config.maximum_spread_percent:.3f}%.",
        ),
        StrategyCondition(
            name="slippage",
            met=candidate.liquidity.estimated_slippage_percent is not None
            and candidate.liquidity.estimated_slippage_percent <= config.maximum_slippage_percent,
            explanation=f"Estimated slippage must be known and no more than {config.maximum_slippage_percent:.3f}%.",
        ),
        StrategyCondition(
            name="liquidity",
            met=candidate.liquidity.classification
            in {LiquidityClassification.EXCELLENT, LiquidityClassification.GOOD, LiquidityClassification.ACCEPTABLE},
            explanation="Liquidity classification must be acceptable or better.",
        ),
    ]
    frame = context.timeframes.get(Timeframe.MINUTE_15)
    regime = frame.volatility.regime if frame and frame.volatility else None
    checks.append(
        StrategyCondition(
            name="volatility_safety",
            met=regime is None or regime.value not in config.disabled_regimes,
            explanation="The 15m volatility regime must not be explicitly disabled.",
        )
    )
    return checks
