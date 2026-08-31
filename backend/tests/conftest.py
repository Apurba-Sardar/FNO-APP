from datetime import UTC, datetime, timedelta

import pytest

from app.domain.market import Candle


@pytest.fixture
def candles() -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    result = []
    for i in range(240):
        close = 100 + i * 0.25
        result.append(
            Candle(
                time=start + timedelta(minutes=5 * i),
                open=close - 0.1,
                high=close + 0.8,
                low=close - 0.8,
                close=close,
                volume=100 + (i % 20) * 5,
            )
        )
    return result
