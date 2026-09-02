from .config import RiskConfig


class FeeEstimator:
    """Configurable round-trip fee estimate; defaults to taker entry and exit."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    @property
    def rate(self) -> float:
        percent = (
            self.config.taker_fee_percent
            if self.config.fee_mode == "taker"
            else self.config.maker_fee_percent
        )
        return percent / 100

    def maximum_loss_fees(self, quantity: float, entry: float, stop: float) -> float:
        return quantity * (entry + stop) * self.rate

    def target_fees(self, quantity: float, entry: float, target: float) -> float:
        return quantity * (entry + target) * self.rate

