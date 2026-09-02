from datetime import UTC, datetime

from app.domain.analysis import ScoreInputs
from app.domain.market import Timeframe
from app.scanner.models import CandidateStatus, LiquidityClassification, ScannerCandidate

from .config import ScoreWeights, ScoringConfig
from .explanations import explain
from .factors import (
    liquidity_factor,
    momentum_factor,
    risk_reward_factor,
    setup_factor,
    support_resistance_factor,
    trend_factor,
    volatility_factor,
    volume_factor,
)
from .models import (
    FactorName,
    Opportunity,
    OpportunityDirection,
    OpportunityTier,
    ScoreFactor,
)


class OpportunityScorer:
    """Phase 1 compatibility adapter for normalized 0–1 ScoreInputs."""

    def __init__(self, weights: ScoreWeights) -> None:
        self.weights = weights

    def score(self, inputs: ScoreInputs) -> tuple[float, dict[str, float]]:
        components = {
            name: round(value * getattr(self.weights, name), 4)
            for name, value in inputs.model_dump().items()
        }
        return round(sum(components.values()), 2), components


class OpportunityScoringEngine:
    """Deterministic, direction-aware Phase 5 analytical scoring engine."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    def score_candidate(self, candidate: ScannerCandidate) -> Opportunity:
        long_factors, long_rr = self._directional_factors(candidate, OpportunityDirection.BULLISH)
        short_factors, short_rr = self._directional_factors(candidate, OpportunityDirection.BEARISH)
        long_score = self._total(long_factors)
        short_score = self._total(short_factors)
        direction = self._direction(candidate, long_score, short_score)
        selected_long = direction != OpportunityDirection.BEARISH and long_score >= short_score
        selected = long_factors if selected_long else short_factors
        selected_rr = long_rr if selected_long else short_rr
        gates = self.hard_gates(candidate)
        eligible = not gates
        score = max(long_score, short_score) if eligible else 0.0
        tier = self.tier(score)
        strongest, weakest, summary = explain(
            candidate.symbol, direction, eligible, selected, gates
        )
        factor_warnings = [warning for factor in selected for warning in factor.warnings]
        return Opportunity(
            symbol=candidate.symbol,
            scan_timestamp=candidate.scan_timestamp,
            calculated_at=datetime.now(UTC),
            opportunity_score=score,
            long_score=long_score,
            short_score=short_score,
            dominant_direction=direction,
            tier=tier,
            eligible=eligible,
            hard_gate_reasons=gates,
            factors=selected,
            long_factors=long_factors,
            short_factors=short_factors,
            strongest_factors=strongest,
            weakest_factors=weakest,
            warnings=list(dict.fromkeys([*candidate.warnings, *factor_warnings, *gates])),
            explanation_summary=summary,
            estimated_structural_rr=selected_rr,
            long_estimated_structural_rr=long_rr,
            short_estimated_structural_rr=short_rr,
            market_activity=candidate.technical_activity,
            liquidity=candidate.liquidity.classification,
            volatility=candidate.volatility.suitability,
            data_quality=candidate.data_quality_status,
            relative_volume=candidate.volume.relative_volume,
            atr_percent=candidate.volatility.atr_percent,
        )

    def _directional_factors(
        self,
        candidate: ScannerCandidate,
        direction: OpportunityDirection,
    ) -> tuple[list[ScoreFactor], float | None]:
        weights = self.config.weights
        weekly = candidate.timeframes.get(Timeframe.WEEK_1)
        daily = candidate.timeframes.get(Timeframe.DAY_1)
        four_hour = candidate.timeframes.get(Timeframe.HOUR_4)
        one_hour = candidate.timeframes.get(Timeframe.HOUR_1)
        fifteen = candidate.timeframes.get(Timeframe.MINUTE_15)
        sr_factor, rr, rr_raw = support_resistance_factor(
            candidate,
            direction,
            weights.support_resistance,
            self.config,
        )
        factors = [
            trend_factor(
                weekly,
                direction,
                FactorName.WEEKLY_TREND,
                weights.weekly_trend,
            ),
            trend_factor(
                daily,
                direction,
                FactorName.DAILY_TREND,
                weights.daily_trend,
            ),
            trend_factor(
                four_hour,
                direction,
                FactorName.FOUR_HOUR_TREND,
                weights.four_hour_trend,
                daily.trend if daily else None,
            ),
            momentum_factor(one_hour, direction, weights.one_hour_momentum),
            setup_factor(fifteen, direction, weights.fifteen_minute_setup),
            volume_factor(candidate, direction, weights.volume_expansion),
            liquidity_factor(candidate, weights.liquidity_order_book),
            volatility_factor(candidate, weights.volatility_atr),
            sr_factor,
            risk_reward_factor(rr, rr_raw, weights.risk_reward, self.config),
        ]
        return factors, rr

    @staticmethod
    def _total(factors: list[ScoreFactor]) -> float:
        return max(0.0, min(100.0, sum(item.weighted_contribution for item in factors)))

    def _direction(
        self, candidate: ScannerCandidate, long_score: float, short_score: float
    ) -> OpportunityDirection:
        difference = abs(long_score - short_score)
        if difference < self.config.direction_difference_threshold:
            return (
                OpportunityDirection.MIXED
                if candidate.dominant_direction.value == "mixed"
                else OpportunityDirection.NEUTRAL
            )
        return (
            OpportunityDirection.BULLISH
            if long_score > short_score
            else OpportunityDirection.BEARISH
        )

    def hard_gates(self, candidate: ScannerCandidate) -> list[str]:
        reasons = []
        if candidate.status != CandidateStatus.ELIGIBLE:
            reasons.append(f"scanner_status_{candidate.status.value}")
        if not candidate.market.fresh:
            reasons.append("stale_market_data")
        if candidate.market.last_price is None:
            reasons.append("invalid_market_price")
        liquidity_order = {
            LiquidityClassification.UNUSABLE: 0,
            LiquidityClassification.POOR: 1,
            LiquidityClassification.ACCEPTABLE: 2,
            LiquidityClassification.GOOD: 3,
            LiquidityClassification.EXCELLENT: 4,
        }
        minimum = LiquidityClassification(self.config.minimum_liquidity)
        if liquidity_order[candidate.liquidity.classification] < liquidity_order[minimum]:
            reasons.append("liquidity_below_minimum")
        spread = candidate.liquidity.spread_percent
        if spread is None:
            reasons.append("spread_unknown")
        elif spread > self.config.maximum_spread_percent:
            reasons.append("extreme_spread")
        if (
            self.config.exclude_extreme_volatility
            and candidate.volatility.suitability.value == "extreme"
        ):
            reasons.append("extreme_volatility")
        if candidate.data_quality_status != "healthy":
            reasons.append("critical_data_quality")
        if len(candidate.timeframes) != len(Timeframe):
            reasons.append("missing_timeframes")
        elif any(
            not item.data_quality.sufficient_data or item.data_quality.stale_data
            for item in candidate.timeframes.values()
        ):
            reasons.append("invalid_or_stale_timeframe")
        return list(dict.fromkeys(reasons))

    def tier(self, score: float) -> OpportunityTier:
        if score >= self.config.tier_a_plus:
            return OpportunityTier.A_PLUS
        if score >= self.config.tier_a:
            return OpportunityTier.A
        if score >= self.config.tier_b:
            return OpportunityTier.B
        if score >= self.config.tier_c:
            return OpportunityTier.C
        return OpportunityTier.D
