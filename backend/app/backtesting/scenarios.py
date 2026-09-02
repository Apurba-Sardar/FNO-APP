from enum import StrEnum

from .config import BacktestConfig, IntrabarPolicy


class ScenarioName(StrEnum):
    BASELINE = "baseline"
    HIGHER_SLIPPAGE = "higher_slippage"
    HIGHER_FEES = "higher_fees"
    LOWER_FEES = "lower_fees"
    WIDER_SPREAD = "wider_spread"
    DELAYED_ENTRY = "delayed_entry"
    WORST_CASE_INTRABAR = "worst_case_intrabar"


def scenario_config(config: BacktestConfig, scenario: ScenarioName) -> BacktestConfig:
    if scenario == ScenarioName.HIGHER_SLIPPAGE:
        slip = config.slippage_model.model_copy(
            update={
                "entry_slippage_bps": config.slippage_model.entry_slippage_bps * 2,
                "exit_slippage_bps": config.slippage_model.exit_slippage_bps * 2,
            }
        )
        return config.model_copy(update={"slippage_model": slip})
    if scenario in {ScenarioName.HIGHER_FEES, ScenarioName.LOWER_FEES}:
        multiple = 2 if scenario == ScenarioName.HIGHER_FEES else 0.5
        fee = config.fee_model.model_copy(
            update={
                "maker_fee_percent": config.fee_model.maker_fee_percent * multiple,
                "taker_fee_percent": config.fee_model.taker_fee_percent * multiple,
            }
        )
        return config.model_copy(update={"fee_model": fee})
    if scenario == ScenarioName.WORST_CASE_INTRABAR:
        return config.model_copy(update={"intrabar_policy": IntrabarPolicy.ASSUME_STOP_FIRST})
    if scenario == ScenarioName.WIDER_SPREAD:
        return config.model_copy(
            update={"historical_spread_percent": config.historical_spread_percent * 2}
        )
    if scenario == ScenarioName.DELAYED_ENTRY:
        return config.model_copy(update={"entry_delay_candles": config.entry_delay_candles + 1})
    return config.model_copy(deep=True)
