from .models import StrategyHealthState


class PerformanceDriftMonitor:
    def __init__(self, minimum_sample: int) -> None:
        self.minimum_sample = minimum_sample

    def evaluate(self, paper: dict, comparison: dict) -> dict:
        if paper["trades"] < self.minimum_sample:
            return {
                "state": StrategyHealthState.INSUFFICIENT_SAMPLE,
                "warnings": [f"Insufficient live sample size ({paper['trades']}/{self.minimum_sample} trades)."],
            }
        if not comparison.get("available"):
            return {
                "state": StrategyHealthState.WARNING,
                "warnings": ["Backtest baseline unavailable; performance drift cannot be evaluated."],
            }
        warnings = []
        deviations = comparison["deviations"]
        if deviations.get("expectancy") is not None and deviations["expectancy"] < 0:
            warnings.append("Paper expectancy has declined versus the backtest baseline.")
        if deviations.get("average_r") is not None and deviations["average_r"] < -0.25:
            warnings.append("Paper average R is materially below the backtest baseline.")
        return {
            "state": StrategyHealthState.WARNING if warnings else StrategyHealthState.HEALTHY,
            "warnings": warnings,
        }
