from datetime import datetime

from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle

from .data_provider import candle_close_time
from .exceptions import FutureDataAccess


class HistoricalMarketContext:
    """Point-in-time view that never exposes an unclosed or future candle."""

    def __init__(
        self,
        symbol: str,
        candles: dict[Timeframe, list[NormalizedCandle]],
        evaluation_timestamp: datetime,
    ) -> None:
        self.symbol = symbol
        self._candles = candles
        self.evaluation_timestamp = evaluation_timestamp

    def closed_candles(self, timeframe: Timeframe, limit: int | None = None):
        rows = [
            row
            for row in self._candles.get(timeframe, [])
            if candle_close_time(row) <= self.evaluation_timestamp
        ]
        return rows[-limit:] if limit else rows

    def candle_at(self, timeframe: Timeframe, open_timestamp: datetime):
        for row in self._candles.get(timeframe, []):
            if row.timestamp == open_timestamp:
                if candle_close_time(row) > self.evaluation_timestamp:
                    raise FutureDataAccess("requested candle had not closed at evaluation time")
                return row
        return None

    def assert_not_future(self, candles: list[NormalizedCandle]) -> None:
        if any(candle_close_time(row) > self.evaluation_timestamp for row in candles):
            raise FutureDataAccess("future candle access blocked")
