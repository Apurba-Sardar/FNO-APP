from datetime import timedelta

import pytest

from app.domain.market import Timeframe
from app.indicators.models import VolatilityRegime
from app.market_data.models import NormalizedCandle
from app.strategy.config import StrategyConfig
from app.strategy.lifecycle import apply_lifecycle
from app.strategy.models import StrategyDirection, StrategyName, StrategyStatus
from tests.phase6_fixtures import strategy_fixture


@pytest.mark.parametrize("slope,direction", [(0.2, StrategyDirection.LONG), (-0.2, StrategyDirection.SHORT)])
def test_strategy_direction_is_deterministic(slope, direction):
    market, opportunity, _, _, engine = strategy_fixture(slope)
    result = engine.evaluate(opportunity, market, market.scan_timestamp)
    assert all(item.direction in {direction, StrategyDirection.NO_SETUP} for item in result.results.values())


def test_hard_liquidity_gate_cannot_be_bypassed_by_score():
    market, opportunity, _, _, engine = strategy_fixture()
    market.liquidity.spread_percent = 10
    opportunity.opportunity_score = 100
    result = engine.evaluate(opportunity, market, market.scan_timestamp)
    assert all(item.status == StrategyStatus.NO_SETUP for item in result.results.values())
    assert all(any(condition.name == "spread" and not condition.met for condition in item.conditions) for item in result.results.values())


def test_breakout_wick_without_close_is_not_triggered():
    market, opportunity, _, _, engine = strategy_fixture()
    rows = market.recent_candles[Timeframe.MINUTE_15]
    boundary = max(candle.high for candle in rows[-22:-2])
    original = rows[-2]
    wick = NormalizedCandle(
        symbol=market.symbol,
        timeframe=Timeframe.MINUTE_15,
        timestamp=original.timestamp,
        open=boundary - 1,
        high=boundary + 5,
        low=boundary - 2,
        close=boundary - 0.2,
        volume=2_000,
    )
    market.recent_candles[Timeframe.MINUTE_15][-2] = wick
    result = engine.evaluate(opportunity, market, market.scan_timestamp).results[StrategyName.BREAKOUT]
    assert result.status != StrategyStatus.TRIGGERED
    assert any(item.name == "close_beyond_level" and not item.met for item in result.conditions)


def test_breakout_closed_candle_confirmation_can_trigger():
    config = StrategyConfig(minimum_setup_quality=0, minimum_risk_reward=0.1)
    market, opportunity, _, _, engine = strategy_fixture(config=config)
    rows = market.recent_candles[Timeframe.MINUTE_15]
    boundary = max(candle.high for candle in rows[-22:-2])
    original = rows[-2]
    breakout = NormalizedCandle(
        symbol=market.symbol,
        timeframe=Timeframe.MINUTE_15,
        timestamp=original.timestamp,
        open=boundary - 0.2,
        high=boundary + 3,
        low=boundary - 0.5,
        close=boundary + 2.5,
        volume=5_000,
    )
    market.recent_candles[Timeframe.MINUTE_15][-2] = breakout
    result = engine.evaluate(opportunity, market, market.scan_timestamp).results[StrategyName.BREAKOUT]
    assert result.status == StrategyStatus.TRIGGERED
    assert result.hypothetical_entry == pytest.approx(breakout.close)
    assert result.hypothetical_stop is not None
    assert result.hypothetical_target is not None


def test_expiry_and_invalidation_are_terminal_lifecycle_states():
    market, opportunity, _, _, engine = strategy_fixture()
    previous = engine.evaluate(opportunity, market, market.scan_timestamp)
    prior = previous.results[StrategyName.TREND_PULLBACK]
    prior.status = StrategyStatus.ARMED
    prior.direction = StrategyDirection.LONG
    prior.invalidation_price = previous.chart[-1].close + 1
    prior.expires_at = market.scan_timestamp + timedelta(minutes=1)
    current = engine.evaluate(opportunity, market, market.scan_timestamp + timedelta(minutes=2))
    transitioned = apply_lifecycle(previous, current)
    assert transitioned.results[StrategyName.TREND_PULLBACK].status == StrategyStatus.INVALIDATED


def test_results_do_not_contain_execution_or_probability_fields():
    market, opportunity, _, _, engine = strategy_fixture()
    payload = engine.evaluate(opportunity, market, market.scan_timestamp).model_dump_json().lower()
    for forbidden in ("order_id", "quantity", "leverage", "win_probability", "buy", "sell"):
        assert forbidden not in payload


def test_identical_inputs_produce_identical_results():
    market, opportunity, _, _, engine = strategy_fixture()
    first = engine.evaluate(opportunity, market, market.scan_timestamp)
    second = engine.evaluate(opportunity, market, market.scan_timestamp)
    assert first == second


def test_extreme_volatility_blocks_both_strategies():
    market, opportunity, _, builder, engine = strategy_fixture()
    context = builder.build(opportunity, market, market.scan_timestamp)
    context.timeframes[Timeframe.MINUTE_15].volatility.regime = VolatilityRegime.EXTREME
    results = [strategy.evaluate(context) for strategy in engine.strategies]
    assert all(result.status == StrategyStatus.NO_SETUP for result in results)
    assert all(any(item.name == "volatility_safety" and not item.met for item in result.conditions) for result in results)


def test_broken_pullback_structure_cannot_trigger():
    market, opportunity, _, builder, engine = strategy_fixture()
    context = builder.build(opportunity, market, market.scan_timestamp)
    context.timeframes[Timeframe.MINUTE_15].structure.lower_low = True
    result = engine.strategies[0].evaluate(context)
    assert result.status != StrategyStatus.TRIGGERED
    assert any(item.name == "structure_intact" and not item.met for item in result.conditions)


@pytest.mark.parametrize(
    "volume,distance_atr,failed_condition",
    [(1, 0.5, "volume_expansion"), (5_000, 3.0, "breakout_distance")],
)
def test_breakout_rejects_low_volume_or_excessive_extension(volume, distance_atr, failed_condition):
    config = StrategyConfig(minimum_setup_quality=0, minimum_risk_reward=0.1)
    market, opportunity, _, builder, engine = strategy_fixture(config=config)
    context = builder.build(opportunity, market, market.scan_timestamp)
    rows = context.candles[Timeframe.MINUTE_15]
    frame = context.timeframes[Timeframe.MINUTE_15]
    boundary = max(candle.high for candle in rows[-21:-1])
    candle = rows[-1]
    close = boundary + frame.indicators.atr * distance_atr
    rows[-1] = candle.model_copy(
        update={"open": boundary - 0.1, "high": close + 0.1, "low": boundary - 0.2, "close": close, "volume": volume}
    )
    context = builder.build(opportunity, context.market.model_copy(update={"recent_candles": context.candles}), market.scan_timestamp)
    result = engine.strategies[1].evaluate(context)
    assert result.status != StrategyStatus.TRIGGERED
    assert any(item.name == failed_condition and not item.met for item in result.conditions)


def test_configured_breakout_retest_confirmation():
    config = StrategyConfig(retest_required=True, minimum_setup_quality=0, minimum_risk_reward=0.1)
    market, opportunity, _, builder, engine = strategy_fixture(config=config)
    rows = market.recent_candles[Timeframe.MINUTE_15]
    boundary = max(candle.high for candle in rows[-23:-3])
    breakout = rows[-3]
    rows[-3] = breakout.model_copy(update={"open": boundary - 0.2, "high": boundary + 2.5, "low": boundary - 0.4, "close": boundary + 2, "volume": 5_000})
    retest = rows[-2]
    rows[-2] = retest.model_copy(update={"open": boundary + 0.5, "high": boundary + 1, "low": boundary - 0.1, "close": boundary + 0.4, "volume": 500})
    context = builder.build(opportunity, market, market.scan_timestamp)
    result = engine.strategies[1].evaluate(context)
    assert any(item.name == "retest_confirmation" and item.met for item in result.conditions)


def test_strategy_package_has_no_execution_or_private_client_imports():
    from pathlib import Path

    root = Path(__file__).parents[2] / "app" / "strategy"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py")).lower()
    for forbidden in ("tradeexecutor", "orderservice", "positionservice", "coindcxpublicclient", "coindcxprivate"):
        assert forbidden not in source
