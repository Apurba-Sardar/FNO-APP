from datetime import timedelta

import pytest

from app.backtesting.context import HistoricalMarketContext
from app.backtesting.exceptions import FutureDataAccess
from app.backtesting.historical import HistoricalCandidateBuilder
from app.backtesting.validation import validate_historical_data
from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION
from app.scoring.engine import OpportunityScoringEngine
from tests.phase8_fixtures import NOW, candle, config


def test_context_exposes_only_closed_candles_and_blocks_future_access():
    row = candle()
    context = HistoricalMarketContext(
        row.symbol, {Timeframe.MINUTE_5: [row]}, NOW + timedelta(minutes=4)
    )
    assert context.closed_candles(Timeframe.MINUTE_5) == []
    with pytest.raises(FutureDataAccess):
        context.candle_at(Timeframe.MINUTE_5, NOW)
    context = HistoricalMarketContext(
        row.symbol, {Timeframe.MINUTE_5: [row]}, NOW + timedelta(minutes=5)
    )
    assert context.closed_candles(Timeframe.MINUTE_5) == [row]


def test_validation_reports_duplicates_gaps_and_missing_frames():
    rows = [candle(), candle(), candle(2)]
    report = validate_historical_data(
        {"B-TEST_USDT": {Timeframe.MINUTE_5: rows}}, minimum_history=5
    )
    assert report.duplicate_candles
    assert report.missing_periods
    assert Timeframe.DAY_1.value in report.unavailable_timeframes["B-TEST_USDT"]
    assert not report.valid


def test_future_prices_volume_indicators_levels_and_scores_cannot_leak():
    base = {}
    with_future = {}
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        rows = [
            NormalizedCandle(
                symbol="B-TEST_USDT",
                timeframe=timeframe,
                timestamp=NOW - (220 - index) * duration,
                open=100 + index * 0.01,
                high=101 + index * 0.01,
                low=99 + index * 0.01,
                close=100.5 + index * 0.01,
                volume=100 + index,
            )
            for index in range(220)
        ]
        future = NormalizedCandle(
            symbol="B-TEST_USDT",
            timeframe=timeframe,
            timestamp=NOW,
            open=1000,
            high=2000,
            low=1,
            close=1500,
            volume=1_000_000,
        )
        base[timeframe] = rows
        with_future[timeframe] = [*rows, future]
    builder = HistoricalCandidateBuilder(config())
    left = builder.build(HistoricalMarketContext("B-TEST_USDT", base, NOW))
    right = builder.build(HistoricalMarketContext("B-TEST_USDT", with_future, NOW))
    assert left.timeframes == right.timeframes
    assert left.volume == right.volume
    assert left.market.last_price == right.market.last_price
    scorer = OpportunityScoringEngine(config().scoring)
    left_score, right_score = scorer.score_candidate(left), scorer.score_candidate(right)
    assert left_score.opportunity_score == right_score.opportunity_score
    assert left_score.factors == right_score.factors
