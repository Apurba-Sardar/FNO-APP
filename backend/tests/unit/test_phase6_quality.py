import pytest

from app.strategy.config import SetupQualityWeights, StrategyConfig
from app.strategy.quality import build_quality, quality_class
from tests.phase6_fixtures import strategy_fixture


def test_quality_weights_must_total_one_hundred():
    with pytest.raises(ValueError):
        SetupQualityWeights(trend_alignment=11)


@pytest.mark.parametrize(
    "score,expected",
    [(95, "excellent"), (85, "good"), (75, "acceptable"), (65, "weak"), (40, "invalid")],
)
def test_quality_classifications(score, expected):
    assert quality_class(score, StrategyConfig()).value == expected


def test_quality_breakdown_is_auditable_and_bounded():
    market, *_ = strategy_fixture()
    score, factors = build_quality(
        StrategyConfig(),
        market,
        trend=80,
        structure=80,
        location=80,
        trigger=80,
        volume=80,
        momentum=80,
        room=80,
        risk_reward=80,
    )
    assert 0 <= score <= 100
    assert len(factors) == 10
    assert sum(item.weight for item in factors) == 100
