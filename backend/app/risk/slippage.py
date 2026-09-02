from .config import MissingDataPolicy, RiskConfig


class SlippageEstimator:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def effective_percent(self, market_percent: float | None) -> tuple[float | None, str | None]:
        if market_percent is None:
            if self.config.missing_slippage_policy == MissingDataPolicy.REJECT:
                return None, "estimated slippage is unavailable"
            return self.config.slippage_safety_buffer_percent, "slippage unavailable; safety buffer used"
        return market_percent + self.config.slippage_safety_buffer_percent, None

    def cost(self, quantity: float, entry: float, effective_percent: float) -> float:
        return (
            quantity
            * entry
            * effective_percent
            / 100
            * self.config.slippage_round_trip_multiplier
        )

