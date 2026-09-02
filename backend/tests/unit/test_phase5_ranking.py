from app.scoring.engine import OpportunityScoringEngine
from app.scoring.ranking import OpportunityRankingService
from tests.phase5_fixtures import candidate


def test_ranking_is_deterministic_and_tracks_score_and_rank_change():
    engine = OpportunityScoringEngine()
    service = OpportunityRankingService()
    first_items = [
        engine.score_candidate(candidate(0.2, "B-Z_USDT")),
        engine.score_candidate(candidate(0.2, "B-A_USDT")),
    ]
    first, _ = service.rank(first_items)
    assert [item.symbol for item in first] == ["B-A_USDT", "B-Z_USDT"]
    previous = {item.symbol: item for item in first}
    second_items = [
        engine.score_candidate(candidate(0.3, "B-Z_USDT")),
        engine.score_candidate(candidate(0.1, "B-A_USDT")),
    ]
    second, _ = service.rank(second_items, previous)
    assert all(item.previous_score is not None for item in second)
    assert all(item.score_change is not None for item in second)
    assert all(item.previous_rank is not None for item in second)


def test_tie_break_uses_liquidity_then_symbol():
    engine = OpportunityScoringEngine()
    service = OpportunityRankingService()
    zulu = engine.score_candidate(candidate(0.2, "B-ZULU_USDT"))
    alpha = engine.score_candidate(candidate(0.2, "B-ALPHA_USDT"))
    ranked, _ = service.rank([zulu, alpha])
    assert [item.symbol for item in ranked] == ["B-ALPHA_USDT", "B-ZULU_USDT"]


def test_rank_change_has_positive_value_when_market_moves_up():
    engine = OpportunityScoringEngine()
    service = OpportunityRankingService()
    alpha = engine.score_candidate(candidate(0.2, "B-ALPHA_USDT")).model_copy(
        update={"opportunity_score": 80}
    )
    beta = engine.score_candidate(candidate(0.2, "B-BETA_USDT")).model_copy(
        update={"opportunity_score": 70}
    )
    first, _ = service.rank([alpha, beta])
    previous = {item.symbol: item for item in first}
    second, _ = service.rank(
        [
            alpha.model_copy(update={"opportunity_score": 75}),
            beta.model_copy(update={"opportunity_score": 85}),
        ],
        previous,
    )
    moved = next(item for item in second if item.symbol == "B-BETA_USDT")
    assert moved.previous_rank == 2
    assert moved.current_rank == 1
    assert moved.rank_change == 1
    assert moved.score_change == 15
