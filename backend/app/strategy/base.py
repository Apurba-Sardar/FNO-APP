from abc import ABC, abstractmethod
from datetime import timedelta

from app.indicators.models import TrendState
from app.scoring.models import OpportunityDirection

from .config import StrategyConfig
from .models import (
    SetupQuality,
    StrategyCondition,
    StrategyContext,
    StrategyDirection,
    StrategyName,
    StrategyResult,
    StrategyStatus,
)


class DeterministicStrategy(ABC):
    name: StrategyName

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyResult: ...

    @staticmethod
    def direction(context: StrategyContext) -> StrategyDirection:
        opportunity = context.opportunity
        if opportunity.dominant_direction == OpportunityDirection.BULLISH:
            return StrategyDirection.LONG
        if opportunity.dominant_direction == OpportunityDirection.BEARISH:
            return StrategyDirection.SHORT
        difference = opportunity.long_score - opportunity.short_score
        if abs(difference) < 3:
            return StrategyDirection.NO_SETUP
        return StrategyDirection.LONG if difference > 0 else StrategyDirection.SHORT

    @staticmethod
    def trend_matches(trend: TrendState, direction: StrategyDirection) -> bool:
        return (direction == StrategyDirection.LONG and trend == TrendState.BULLISH) or (
            direction == StrategyDirection.SHORT and trend == TrendState.BEARISH
        )

    def no_setup(
        self,
        context: StrategyContext,
        conditions: list[StrategyCondition],
        explanations: list[str],
        *,
        direction: StrategyDirection = StrategyDirection.NO_SETUP,
        quality_score: float = 0,
        warnings: list[str] | None = None,
    ) -> StrategyResult:
        return StrategyResult(
            symbol=context.symbol,
            strategy=self.name,
            status=StrategyStatus.NO_SETUP,
            direction=direction,
            evaluation_timestamp=context.evaluation_timestamp,
            opportunity_score=context.opportunity.opportunity_score,
            setup_quality_score=quality_score,
            quality=SetupQuality.INVALID,
            expires_at=context.evaluation_timestamp
            + timedelta(minutes=self.config.setup_expiry_minutes),
            conditions=conditions,
            explanations=explanations,
            warnings=list(dict.fromkeys([*context.warnings, *(warnings or [])])),
        )
