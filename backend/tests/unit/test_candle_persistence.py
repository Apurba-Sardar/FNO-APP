import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import InstrumentModel, MarketCandle
from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from app.market_data.repository import CandleRepository


def test_database_prevents_duplicate_candles():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    with Session(engine) as session:
        session.add(InstrumentModel(pair="B-BTC_USDT", status="active", margin_currency="USDT"))
        session.commit()
        values = {
            "pair": "B-BTC_USDT",
            "timeframe": "15m",
            "open_time": timestamp,
            "open": 100,
            "high": 110,
            "low": 90,
            "close": 105,
            "volume": 10,
        }
        session.add(MarketCandle(**values))
        session.commit()
        session.add(MarketCandle(**values))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.asyncio
async def test_repository_serializes_concurrent_writes():
    session = AsyncMock()
    repository = CandleRepository(session)
    active_writes = 0
    maximum_active_writes = 0

    async def simulated_write(candles):
        nonlocal active_writes, maximum_active_writes
        active_writes += 1
        maximum_active_writes = max(maximum_active_writes, active_writes)
        await asyncio.sleep(0)
        active_writes -= 1
        return len(candles)

    repository._save = simulated_write
    candle = NormalizedCandle(
        symbol="B-BTC_USDT",
        timeframe=Timeframe.MINUTE_5,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1,
    )

    assert await asyncio.gather(repository.save([candle]), repository.save([candle])) == [1, 1]
    assert maximum_active_writes == 1
