from datetime import timedelta

from app.backtesting.monte_carlo import trade_order_monte_carlo
from app.backtesting.scenarios import ScenarioName, scenario_config
from app.backtesting.sensitivity import parameter_variants
from app.backtesting.walk_forward import build_walk_forward_windows
from tests.phase8_fixtures import NOW, config


def test_scenarios_change_execution_assumptions_without_strategy_mutation():
    baseline = config()
    stressed = scenario_config(baseline, ScenarioName.HIGHER_SLIPPAGE)
    delayed = scenario_config(baseline, ScenarioName.DELAYED_ENTRY)
    wider = scenario_config(baseline, ScenarioName.WIDER_SPREAD)
    assert stressed.slippage_model.entry_slippage_bps == 10
    assert delayed.entry_delay_candles == 2
    assert wider.historical_spread_percent == 0.1
    assert stressed.strategy == baseline.strategy


def test_manual_sensitivity_returns_all_variants_without_selecting_one():
    rows = parameter_variants(config(), [1.5, 1.75, 2.0])
    assert [item.risk.minimum_risk_reward for item in rows] == [1.5, 1.75, 2.0]


def test_walk_forward_separates_in_sample_and_out_of_sample():
    rows = build_walk_forward_windows(NOW, NOW + timedelta(days=120), 60, 20)
    assert rows
    assert all(item.in_sample_end == item.out_of_sample_start for item in rows)
    assert all(item.out_of_sample_end <= NOW + timedelta(days=120) for item in rows)


def test_monte_carlo_is_seeded_and_explicitly_not_predictive():
    first = trade_order_monte_carlo([100, -50, 25, -10], 100_000, runs=100, seed=7)
    second = trade_order_monte_carlo([100, -50, 25, -10], 100_000, runs=100, seed=7)
    assert first == second
    assert "not a future prediction" in first["warning"]
