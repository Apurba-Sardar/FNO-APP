from time import perf_counter
from typing import ClassVar

from app.scanner.models import LiquidityClassification

from .models import Opportunity


class OpportunityRankingService:
    LIQUIDITY_ORDER: ClassVar = {
        LiquidityClassification.EXCELLENT: 4,
        LiquidityClassification.GOOD: 3,
        LiquidityClassification.ACCEPTABLE: 2,
        LiquidityClassification.POOR: 1,
        LiquidityClassification.UNUSABLE: 0,
    }

    def rank(
        self,
        opportunities: list[Opportunity],
        previous: dict[str, Opportunity] | None = None,
    ) -> tuple[list[Opportunity], float]:
        started = perf_counter()
        previous = previous or {}
        eligible = sorted(
            (item for item in opportunities if item.eligible),
            key=lambda item: (
                -item.opportunity_score,
                -self.LIQUIDITY_ORDER[item.liquidity],
                0 if item.data_quality == "healthy" else 1,
                -(item.estimated_structural_rr or -1),
                item.symbol,
            ),
        )
        ranks = {item.symbol: index for index, item in enumerate(eligible, start=1)}
        updated = []
        for item in opportunities:
            old = previous.get(item.symbol)
            current_rank = ranks.get(item.symbol)
            previous_rank = old.current_rank if old else None
            updated.append(
                item.model_copy(
                    update={
                        "previous_score": old.opportunity_score if old else None,
                        "score_change": (
                            item.opportunity_score - old.opportunity_score if old else None
                        ),
                        "previous_rank": previous_rank,
                        "current_rank": current_rank,
                        "rank_change": (
                            previous_rank - current_rank
                            if previous_rank is not None and current_rank is not None
                            else None
                        ),
                    }
                )
            )
        updated.sort(
            key=lambda item: (
                not item.eligible,
                item.current_rank or 10**9,
                item.symbol,
            )
        )
        return updated, (perf_counter() - started) * 1000
