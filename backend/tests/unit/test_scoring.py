import pytest
from pydantic import ValidationError

from app.config import ScoreWeights
from app.domain.analysis import ScoreInputs
from app.scoring.engine import OpportunityScorer


def test_default_weights_total_100():
    score, components = OpportunityScorer(ScoreWeights()).score(
        ScoreInputs(**{name: 1 for name in ScoreWeights.model_fields})
    )
    assert score == 100
    assert sum(components.values()) == 100


def test_partial_score_is_weighted_not_boolean():
    inputs = {name: 0 for name in ScoreWeights.model_fields}
    inputs["daily_trend"] = 0.5
    score, _ = OpportunityScorer(ScoreWeights()).score(ScoreInputs(**inputs))
    assert score == 7.5


def test_invalid_weight_total_fails_configuration():
    with pytest.raises(ValidationError):
        ScoreWeights(weekly_trend=9)
