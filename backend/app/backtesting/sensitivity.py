from .config import BacktestConfig


def parameter_variants(config: BacktestConfig, minimum_rr_values: list[float]):
    """Returns explicit variants without selecting or ranking a winner."""
    return [
        config.model_copy(
            update={
                "risk": config.risk.model_copy(update={"minimum_risk_reward": value}),
                "strategy": config.strategy.model_copy(update={"minimum_risk_reward": value}),
            }
        )
        for value in minimum_rr_values
    ]
