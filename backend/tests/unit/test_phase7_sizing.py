import pytest

from app.risk.config import RiskConfig
from app.risk.fees import FeeEstimator
from app.risk.position_sizing import PositionSizer, round_quantity_down
from app.risk.slippage import SlippageEstimator
from app.strategy.models import StrategyDirection
from tests.phase7_fixtures import context, decision, instrument


def test_risk_budget_is_half_percent_of_equity():
    result = decision()
    assert result.risk_amount == 500
    assert result.risk_percent == 0.5


@pytest.mark.parametrize("direction", [StrategyDirection.LONG, StrategyDirection.SHORT])
def test_long_and_short_position_sizing(direction):
    result = decision(direction=direction)
    assert result.allowed
    assert result.position_quantity > 0
    assert result.maximum_loss <= result.risk_amount
    assert result.estimated_rr == 2


def test_fees_and_slippage_are_included_in_maximum_loss():
    result = decision()
    assert result.estimated_fees > 0
    assert result.estimated_slippage_cost > 0
    assert result.maximum_loss == pytest.approx(
        result.stop_loss_risk + result.estimated_fees + result.estimated_slippage_cost
    )


def test_fee_and_slippage_configuration_is_explicit():
    config = RiskConfig(taker_fee_percent=0.1, slippage_safety_buffer_percent=0.1)
    assert FeeEstimator(config).rate == pytest.approx(0.001)
    assert SlippageEstimator(config).effective_percent(0.2)[0] == pytest.approx(0.3)


def test_quantity_always_rounds_down():
    assert round_quantity_down(123.456789, 0.001) == 123.456
    assert round_quantity_down(0.0009, 0.001) == 0


def test_minimum_quantity_and_notional_reject_without_increasing_risk():
    too_large = instrument(min_quantity=1_000)
    result = decision(instrument=too_large)
    assert not result.allowed
    assert any(item.name == "MINIMUM_QUANTITY" and not item.passed for item in result.checks)
    assert result.position_quantity < 1_000
    expensive = decision(instrument=instrument(min_notional=50_000))
    assert not expensive.allowed
    assert any(item.name == "MINIMUM_NOTIONAL" and not item.passed for item in expensive.checks)


def test_maximum_notional_caps_quantity_and_recalculates_loss():
    result = decision(config=RiskConfig(max_position_notional=10_000))
    assert result.allowed
    assert result.position_notional <= 10_000
    assert result.maximum_loss < result.risk_amount


def test_missing_contract_step_rejects():
    result = decision(instrument=instrument(step_size=None, quantity_precision=None))
    assert not result.allowed
    assert result.position_quantity == 0


def test_position_sizer_never_exceeds_budget_after_rounding():
    config = RiskConfig()
    size = PositionSizer(config).calculate(
        entry=100,
        stop=99,
        risk_budget=500,
        effective_slippage_percent=0.1,
        instrument=instrument(),
        maximum_new_notional=100_000,
    )
    assert size.maximum_loss <= 500


def test_wider_stop_never_increases_quantity():
    narrow = decision()
    wide_context = context()
    wide_context.strategy_setup.hypothetical_stop = 98
    wide_context.atr = 1
    wide = __import__("app.risk.engine", fromlist=["RiskEngine"]).RiskEngine(RiskConfig()).evaluate(wide_context)
    assert wide.position_quantity <= narrow.position_quantity
