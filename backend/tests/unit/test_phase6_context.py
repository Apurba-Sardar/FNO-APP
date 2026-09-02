from datetime import timedelta

from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from tests.phase6_fixtures import strategy_fixture


def test_context_uses_completed_candles_only():
    market, opportunity, _, builder, _ = strategy_fixture()
    evaluation = market.scan_timestamp
    context = builder.build(opportunity, market, evaluation)
    for timeframe, candles in context.candles.items():
        from app.market_data.normalization import TIMEFRAME_DURATION

        assert all(candle.timestamp + TIMEFRAME_DURATION[timeframe] <= evaluation for candle in candles)


def test_future_candle_cannot_change_analysis():
    market, opportunity, _, builder, _ = strategy_fixture()
    evaluation = market.scan_timestamp
    before = builder.build(opportunity, market, evaluation)
    rows = market.recent_candles[Timeframe.MINUTE_5]
    future = NormalizedCandle(
        symbol=market.symbol,
        timeframe=Timeframe.MINUTE_5,
        timestamp=evaluation + timedelta(minutes=5),
        open=1_000,
        high=2_000,
        low=500,
        close=1_900,
        volume=1_000_000,
    )
    changed = market.model_copy(deep=True)
    changed.recent_candles[Timeframe.MINUTE_5] = [*rows, future]
    after = builder.build(opportunity, changed, evaluation)
    assert before.current_price == after.current_price
    assert before.timeframes[Timeframe.MINUTE_5] == after.timeframes[Timeframe.MINUTE_5]
    assert before.chart == after.chart


def test_future_support_resistance_cannot_be_used():
    market, opportunity, _, builder, _ = strategy_fixture()
    evaluation = market.scan_timestamp
    baseline = builder.build(opportunity, market, evaluation)
    future_market = market.model_copy(deep=True)
    last = future_market.recent_candles[Timeframe.MINUTE_15][-1]
    future_market.recent_candles[Timeframe.MINUTE_15].append(
        last.model_copy(
            update={
                "timestamp": evaluation + timedelta(minutes=15),
                "high": last.high * 5,
                "low": last.low / 2,
                "close": last.close * 2,
            }
        )
    )
    actual = builder.build(opportunity, future_market, evaluation)
    assert baseline.timeframes[Timeframe.MINUTE_15].structure == actual.timeframes[Timeframe.MINUTE_15].structure


def test_future_volume_and_trigger_cannot_be_used():
    market, opportunity, _, builder, _ = strategy_fixture()
    evaluation = market.scan_timestamp
    baseline = builder.build(opportunity, market, evaluation)
    changed = market.model_copy(deep=True)
    last = changed.recent_candles[Timeframe.MINUTE_5][-1]
    changed.recent_candles[Timeframe.MINUTE_5].append(
        last.model_copy(
            update={
                "timestamp": evaluation + timedelta(minutes=5),
                "open": last.close,
                "high": last.close * 1.2,
                "close": last.close * 1.19,
                "volume": 10_000_000,
            }
        )
    )
    actual = builder.build(opportunity, changed, evaluation)
    assert baseline.timeframes[Timeframe.MINUTE_5].indicators == actual.timeframes[Timeframe.MINUTE_5].indicators
    assert baseline.current_price == actual.current_price


def test_snapshot_newer_than_evaluation_is_rejected_by_quality_context():
    market, opportunity, _, builder, _ = strategy_fixture()
    context = builder.build(opportunity, market, market.scan_timestamp - timedelta(minutes=1))
    assert "market snapshot is newer than evaluation timestamp" in context.warnings


def test_context_has_real_indicator_chart_series():
    market, opportunity, _, builder, _ = strategy_fixture()
    context = builder.build(opportunity, market, market.scan_timestamp)
    assert context.chart
    assert context.chart[-1].ema20 is not None
    assert context.chart[-1].ema50 is not None
    assert context.chart[-1].vwap is not None
