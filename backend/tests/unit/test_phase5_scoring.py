from math import inf, nan

import pytest
from pydantic import ValidationError

from app.domain.market import Timeframe
from app.indicators.models import LevelType, PriceLevel
from app.scanner.models import (
    CandidateStatus,
    LiquidityClassification,
    VolatilitySuitability,
)
from app.scoring.config import ScoreWeights, ScoringConfig
from app.scoring.engine import OpportunityScoringEngine
from app.scoring.factors import clamp
from app.scoring.models import OpportunityDirection
from tests.phase5_fixtures import candidate


def test_strong_bullish_and_bearish_are_directionally_symmetric():
    engine = OpportunityScoringEngine()
    bullish = engine.score_candidate(candidate(0.2, "B-BULL_USDT"))
    bearish = engine.score_candidate(candidate(-0.2, "B-BEAR_USDT"))
    assert bullish.dominant_direction == OpportunityDirection.BULLISH
    assert bullish.long_score > bullish.short_score
    assert bearish.dominant_direction == OpportunityDirection.BEARISH
    assert bearish.short_score > bearish.long_score
    assert 0 <= bullish.opportunity_score <= 100
    assert 0 <= bearish.opportunity_score <= 100


def test_all_factors_are_normalized_and_reconstruct_final_score():
    result = OpportunityScoringEngine().score_candidate(candidate())
    assert len(result.factors) == 10
    assert all(0 <= factor.normalized_score <= 100 for factor in result.factors)
    assert all(0 <= factor.weighted_contribution <= factor.weight for factor in result.factors)
    assert result.opportunity_score == pytest.approx(
        sum(factor.weighted_contribution for factor in result.factors)
    )


@pytest.mark.parametrize("invalid", [nan, inf, -inf])
def test_invalid_factor_values_are_rejected(invalid):
    with pytest.raises(ValueError):
        clamp(invalid)


def test_weight_and_tier_configuration_validation():
    with pytest.raises(ValidationError):
        ScoreWeights(weekly_trend=9)
    with pytest.raises(ValidationError):
        ScoringConfig(tier_c=80)
    engine = OpportunityScoringEngine()
    assert engine.tier(95) == "A+"
    assert engine.tier(85) == "A"
    assert engine.tier(75) == "B"
    assert engine.tier(65) == "C"
    assert engine.tier(55) == "D"


def test_hard_gate_prevents_poor_liquidity_from_receiving_final_score():
    fixture = candidate().model_copy(
        update={
            "liquidity": candidate().liquidity.model_copy(
                update={"classification": LiquidityClassification.POOR}
            )
        }
    )
    result = OpportunityScoringEngine().score_candidate(fixture)
    assert not result.eligible
    assert result.opportunity_score == 0
    assert "liquidity_below_minimum" in result.hard_gate_reasons


def test_extreme_spread_and_volatility_are_hard_exclusions():
    fixture = candidate()
    fixture = fixture.model_copy(
        update={
            "liquidity": fixture.liquidity.model_copy(update={"spread_percent": 0.5}),
            "volatility": fixture.volatility.model_copy(
                update={"suitability": VolatilitySuitability.EXTREME}
            ),
        }
    )
    result = OpportunityScoringEngine().score_candidate(fixture)
    assert not result.eligible
    assert {"extreme_spread", "extreme_volatility"} <= set(result.hard_gate_reasons)


def test_missing_data_and_null_structural_rr_are_safe():
    fixture = candidate().model_copy(
        update={
            "status": CandidateStatus.INSUFFICIENT_DATA,
            "timeframes": {},
            "data_quality_status": "insufficient_data",
        }
    )
    result = OpportunityScoringEngine().score_candidate(fixture)
    assert not result.eligible
    assert result.estimated_structural_rr is None
    assert result.opportunity_score == 0


def test_scoring_does_not_mutate_scanner_candidate():
    fixture = candidate()
    before = fixture.model_dump_json()
    OpportunityScoringEngine().score_candidate(fixture)
    assert fixture.model_dump_json() == before


def test_explanation_is_deterministic_and_contains_no_probability_claim():
    engine = OpportunityScoringEngine()
    fixture = candidate()
    first = engine.score_candidate(fixture)
    second = engine.score_candidate(fixture)
    assert first.explanation_summary == second.explanation_summary
    text = first.model_dump_json().lower()
    assert "win_probability" not in text
    assert "profit_probability" not in text
    assert "trade_signal" not in text


def test_custom_weights_change_contributions_but_remain_bounded():
    config = ScoringConfig(
        weights=ScoreWeights(
            weekly_trend=20,
            daily_trend=20,
            four_hour_trend=20,
            one_hour_momentum=5,
            fifteen_minute_setup=5,
            volume_expansion=5,
            liquidity_order_book=10,
            volatility_atr=5,
            support_resistance=5,
            risk_reward=5,
        )
    )
    result = OpportunityScoringEngine(config).score_candidate(candidate())
    weekly = next(item for item in result.factors if item.factor_name == "weekly_trend")
    assert weekly.weight == 20
    assert 0 <= result.opportunity_score <= 100


def test_low_volatility_is_scored_low_without_becoming_a_trade_rule():
    fixture = candidate()
    fixture = fixture.model_copy(
        update={
            "volatility": fixture.volatility.model_copy(
                update={"suitability": VolatilitySuitability.TOO_LOW}
            )
        }
    )
    result = OpportunityScoringEngine().score_candidate(fixture)
    factor = next(item for item in result.factors if item.factor_name == "volatility_atr")
    assert factor.normalized_score == 20


def test_nearby_opposing_level_reduces_support_resistance_quality():
    fixture = candidate()
    frame = fixture.timeframes[Timeframe.MINUTE_15]
    price = fixture.market.last_price
    resistance = PriceLevel(
        price=price + fixture.volatility.atr * 0.1,
        type=LevelType.POTENTIAL_RESISTANCE,
        distance_percent=0.01,
        strength=3,
        timestamp=fixture.scan_timestamp,
        source="test",
    )
    structure = frame.structure.model_copy(
        update={"resistance_levels": [resistance, *frame.structure.resistance_levels]}
    )
    fixture = fixture.model_copy(
        update={
            "timeframes": {
                **fixture.timeframes,
                Timeframe.MINUTE_15: frame.model_copy(update={"structure": structure}),
            }
        }
    )
    result = OpportunityScoringEngine().score_candidate(fixture)
    factor = next(item for item in result.long_factors if item.factor_name == "support_resistance")
    assert factor.normalized_score == 25
    assert "nearby_opposing_level" in factor.warnings


@pytest.mark.parametrize("slope", [-0.4, -0.2, -0.05, 0, 0.05, 0.2, 0.4])
def test_score_and_factor_invariants_across_market_shapes(slope):
    result = OpportunityScoringEngine().score_candidate(candidate(slope))
    assert 0 <= result.opportunity_score <= 100
    assert 0 <= result.long_score <= 100
    assert 0 <= result.short_score <= 100
    for factor in [*result.long_factors, *result.short_factors]:
        assert 0 <= factor.normalized_score <= 100
        assert 0 <= factor.weighted_contribution <= factor.weight
