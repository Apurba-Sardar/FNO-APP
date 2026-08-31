from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import InstrumentModel, MarketCandle


def test_database_prevents_duplicate_candles():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    with Session(engine) as session:
        session.add(InstrumentModel(pair="B-BTC_USDT", status="active", margin_currency="USDT"))
        session.commit()
        values = dict(
            pair="B-BTC_USDT",
            timeframe="15m",
            open_time=timestamp,
            open=100,
            high=110,
            low=90,
            close=105,
            volume=10,
        )
        session.add(MarketCandle(**values))
        session.commit()
        session.add(MarketCandle(**values))
        with pytest.raises(IntegrityError):
            session.commit()
