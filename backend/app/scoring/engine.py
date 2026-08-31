from app.config import ScoreWeights
from app.domain.analysis import ScoreInputs


class OpportunityScorer:
    def __init__(self, weights: ScoreWeights) -> None:
        self.weights = weights

    def score(self, inputs: ScoreInputs) -> tuple[float, dict[str, float]]:
        components = {
            name: round(value * getattr(self.weights, name), 4)
            for name, value in inputs.model_dump().items()
        }
        return round(sum(components.values()), 2), components
