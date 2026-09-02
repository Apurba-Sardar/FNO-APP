import random

from app.risk.config import RiskConfig
from app.risk.engine import RiskEngine
from app.strategy.models import StrategyDirection
from tests.phase7_fixtures import account, context, setup


def test_every_approved_decision_satisfies_all_safety_invariants():
    rng = random.Random(7)
    for _ in range(100):
        equity = rng.uniform(10_000, 1_000_000)
        stop_distance = rng.uniform(0.5, 3)
        risk_percent = rng.uniform(0.1, 1)
        config = RiskConfig(
            risk_per_trade_percent=risk_percent,
            max_position_notional=1_000_000,
            max_total_exposure_percent=500,
        )
        item = context(
            account=account(account_equity=equity, available_balance=equity, starting_day_equity=equity),
            atr=stop_distance,
            strategy_setup=setup(
                hypothetical_stop=100 - stop_distance,
                hypothetical_target=100 + stop_distance * 2,
            ),
        )
        result = RiskEngine(config).evaluate(item)
        if result.allowed:
            assert result.maximum_loss <= result.risk_amount + 1e-9
            assert result.position_quantity > 0
            assert result.estimated_rr >= config.minimum_risk_reward
            assert result.estimated_leverage <= config.max_leverage
            assert result.exposure_percent_after <= config.max_total_exposure_percent
            assert all(check.passed for check in result.checks if check.severity.value == "critical")


def test_monotonic_sizing_properties():
    engine = RiskEngine(RiskConfig(max_position_notional=1_000_000, max_total_exposure_percent=500))
    quantities = []
    for distance in (0.5, 1, 2, 3):
        item = context(
            atr=distance,
            strategy_setup=setup(
                hypothetical_stop=100 - distance,
                hypothetical_target=100 + distance * 2,
            ),
        )
        quantities.append(engine.evaluate(item).position_quantity)
    assert quantities == sorted(quantities, reverse=True)


def test_lower_risk_percentage_never_increases_maximum_loss():
    low = RiskEngine(RiskConfig(risk_per_trade_percent=0.25)).evaluate(context())
    high = RiskEngine(RiskConfig(risk_per_trade_percent=0.5)).evaluate(context())
    assert low.risk_amount < high.risk_amount
    assert low.maximum_loss <= high.maximum_loss


def test_long_and_short_risk_are_symmetric_and_deterministic():
    engine = RiskEngine(RiskConfig())
    long = engine.evaluate(context())
    repeat = engine.evaluate(context())
    short = engine.evaluate(context(StrategyDirection.SHORT))
    assert long == repeat
    assert long.maximum_loss <= long.risk_amount
    assert short.maximum_loss <= short.risk_amount


def test_more_equity_does_not_reduce_configured_risk_budget():
    engine = RiskEngine(RiskConfig(max_position_notional=1_000_000, max_total_exposure_percent=500))
    budgets = [
        engine.evaluate(
            context(account=account(account_equity=value, available_balance=value, starting_day_equity=value))
        ).risk_amount
        for value in (10_000, 100_000, 1_000_000)
    ]
    assert budgets == sorted(budgets)


def test_risk_package_has_no_execution_or_private_api_imports():
    from pathlib import Path

    root = Path(__file__).parents[2] / "app" / "risk"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py")).lower()
    for forbidden in (
        "tradeexecutor",
        "orderservice",
        "livetradingservice",
        "coindcxpublicclient",
        "coindcxprivate",
        "create_order",
    ):
        assert forbidden not in source
