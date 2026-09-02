from datetime import timedelta
from pathlib import Path

from app.backtesting.data_provider import InMemoryHistoricalDataProvider
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import BacktestStatus
from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION
from tests.phase8_fixtures import NOW, config


def dataset():
    rows = {}
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        candles = []
        for index in range(-220, 7 if timeframe == Timeframe.MINUTE_5 else 0):
            price = 100 + index * 0.001
            candles.append(
                NormalizedCandle(
                    symbol="B-TEST_USDT",
                    timeframe=timeframe,
                    timestamp=NOW + index * duration,
                    open=price,
                    high=price + 0.2,
                    low=price - 0.2,
                    close=price + 0.05,
                    volume=100,
                )
            )
        rows[("B-TEST_USDT", timeframe)] = candles
    return rows


async def test_event_engine_is_reproducible_and_uses_existing_phase_engines():
    cfg = config(end_timestamp=NOW + timedelta(minutes=30))
    provider = InMemoryHistoricalDataProvider(dataset())
    first = await BacktestEngine(provider).run(cfg)
    second = await BacktestEngine(provider).run(cfg)
    assert first.status == second.status == BacktestStatus.COMPLETED
    assert first.performance.model_dump() == second.performance.model_dump()
    assert first.counters.model_dump() == second.counters.model_dump()
    assert first.data_quality.candles_checked > 1200
    source = Path("app/backtesting/engine.py").read_text()
    assert "OpportunityScoringEngine" in source
    assert "StrategyEngine" in source
    assert "RiskEngine" in source
    assert "PositionSizer" not in source


def test_backtest_package_has_no_private_or_execution_dependency():
    text = "\n".join(
        path.read_text() for path in Path("app/backtesting").glob("*.py")
    ).lower()
    for forbidden in ("coindcxtrad", "create_order", "cancel_order", "tradeexecutor", "private_client"):
        assert forbidden not in text
