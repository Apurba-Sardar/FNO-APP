from datetime import timedelta

import pytest

from app.risk.config import MissingDataPolicy, RiskConfig
from app.risk.models import AccountSnapshot, OpenPosition, RiskDecisionStatus
from app.strategy.models import StrategyDirection, StrategyStatus
from tests.phase7_fixtures import NOW, account, decision, setup


def failed(result, name):
    return any(item.name == name and not item.passed for item in result.checks)


def test_missing_account_equity_or_balance_fails_safe():
    result = decision(account=AccountSnapshot())
    assert not result.allowed
    assert result.status == RiskDecisionStatus.ACCOUNT_DATA_UNAVAILABLE
    assert failed(result, "ACCOUNT_EQUITY")


def test_daily_loss_limit_includes_fees_and_negative_unrealized_pnl():
    result = decision(
        account=account(realized_pnl_today=-1_500, unrealized_pnl=-400, fees_today=100)
    )
    assert not result.allowed
    assert result.status == RiskDecisionStatus.RISK_LIMIT_REACHED
    assert failed(result, "DAILY_LOSS")


def test_consecutive_loss_limit_and_explicit_cooldown():
    blocked = decision(account=account(consecutive_losses=3))
    assert failed(blocked, "CONSECUTIVE_LOSSES")
    resumed = decision(
        account=account(consecutive_losses=3, consecutive_loss_reset_at=NOW - timedelta(seconds=1))
    )
    assert not failed(resumed, "CONSECUTIVE_LOSSES")


def test_open_position_and_duplicate_symbol_limits_use_confirmed_state():
    position = OpenPosition(
        symbol="B-TEST_USDT",
        direction=StrategyDirection.SHORT,
        notional=10_000,
    )
    result = decision(account=account(open_positions=[position]))
    assert failed(result, "OPEN_POSITIONS")
    assert failed(result, "SYMBOL_EXPOSURE")


def test_total_exposure_limit_is_never_bypassed():
    position = OpenPosition(
        symbol="B-OTHER_USDT",
        direction=StrategyDirection.LONG,
        notional=99_999,
    )
    result = decision(
        config=RiskConfig(max_open_positions=3),
        account=account(open_positions=[position]),
    )
    assert result.position_notional <= 1
    assert result.exposure_percent_after <= 100
    assert not result.allowed  # minimum order constraints fail rather than increasing exposure


def test_leverage_and_margin_do_not_expand_risk_budget():
    low_balance = decision(account=account(available_balance=1_000))
    assert failed(low_balance, "LEVERAGE")
    assert failed(low_balance, "MARGIN")
    assert low_balance.maximum_loss <= low_balance.risk_amount
    higher_ceiling = decision(
        config=RiskConfig(max_leverage=50),
        account=account(available_balance=1_000),
    )
    assert higher_ceiling.risk_amount == low_balance.risk_amount
    assert higher_ceiling.maximum_loss == pytest.approx(low_balance.maximum_loss)


def test_market_quality_and_missing_data_policies():
    assert failed(decision(spread_percent=1), "SPREAD")
    assert failed(decision(estimated_slippage_percent=1), "SLIPPAGE")
    assert failed(decision(estimated_slippage_percent=None), "SLIPPAGE")
    warning = decision(
        config=RiskConfig(missing_slippage_policy=MissingDataPolicy.ALLOW_WITH_WARNING),
        estimated_slippage_percent=None,
    )
    assert warning.allowed
    assert warning.status == RiskDecisionStatus.WARNING


def test_setup_age_price_drift_and_market_freshness():
    stale_setup = setup(
        evaluation_timestamp=NOW - timedelta(minutes=61),
        expires_at=NOW + timedelta(minutes=1),
    )
    assert failed(decision(strategy_setup=stale_setup), "SETUP_AGE")
    assert failed(decision(current_price=101), "PRICE_DRIFT")
    assert failed(decision(market_data_timestamp=NOW - timedelta(minutes=6)), "MARKET_DATA_FRESHNESS")


def test_missing_or_invalid_entry_stop_target_and_rr():
    assert failed(decision(strategy_setup=setup(hypothetical_entry=None)), "ENTRY_VALIDITY")
    assert failed(decision(strategy_setup=setup(hypothetical_stop=None)), "STOP_VALIDITY")
    assert failed(decision(strategy_setup=setup(hypothetical_target=None)), "TARGET_VALIDITY")
    assert failed(decision(strategy_setup=setup(hypothetical_stop=101)), "STOP_VALIDITY")
    assert failed(decision(strategy_setup=setup(hypothetical_target=99)), "TARGET_VALIDITY")
    assert failed(decision(strategy_setup=setup(hypothetical_target=100.5)), "RR")


def test_only_triggered_setups_are_eligible():
    result = decision(strategy_setup=setup(status=StrategyStatus.ARMED))
    assert not result.allowed
    assert failed(result, "SETUP_STATUS")
