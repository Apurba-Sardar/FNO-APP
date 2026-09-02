from datetime import datetime
from typing import Protocol

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InstrumentModel, MarketCandle
from app.domain.market import Timeframe
from app.market_data.models import Market, MarketType, NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION


class HistoricalDataProvider(Protocol):
    async def get_candles(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[NormalizedCandle]: ...

    async def get_available_range(
        self, symbol: str, timeframe: Timeframe
    ) -> tuple[datetime | None, datetime | None]: ...

    async def get_symbols(self) -> list[str]: ...


class DatabaseHistoricalDataProvider:
    """Read-only provider over normalized Phase 2 PostgreSQL candles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_candles(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[NormalizedCandle]:
        result = await self.session.execute(
            select(MarketCandle)
            .where(
                MarketCandle.pair == symbol,
                MarketCandle.timeframe == timeframe.value,
                MarketCandle.open_time >= start,
                MarketCandle.open_time < end,
            )
            .order_by(MarketCandle.open_time)
        )
        return [
            NormalizedCandle(
                symbol=row.pair,
                timeframe=timeframe,
                timestamp=row.open_time,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in result.scalars()
        ]

    async def get_candles_with_warmup(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        warmup: int,
    ) -> list[NormalizedCandle]:
        warmup_rows = await self.session.execute(
            select(MarketCandle)
            .where(
                MarketCandle.pair == symbol,
                MarketCandle.timeframe == timeframe.value,
                MarketCandle.open_time < start,
            )
            .order_by(MarketCandle.open_time.desc())
            .limit(warmup)
        )
        historical = list(reversed(list(warmup_rows.scalars())))
        current = await self.session.execute(
            select(MarketCandle)
            .where(
                MarketCandle.pair == symbol,
                MarketCandle.timeframe == timeframe.value,
                MarketCandle.open_time >= start,
                MarketCandle.open_time < end,
            )
            .order_by(MarketCandle.open_time)
        )
        rows = [*historical, *current.scalars()]
        return [
            NormalizedCandle(
                symbol=row.pair,
                timeframe=timeframe,
                timestamp=row.open_time,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in rows
        ]

    async def get_available_range(
        self, symbol: str, timeframe: Timeframe
    ) -> tuple[datetime | None, datetime | None]:
        row = await self.session.execute(
            select(func.min(MarketCandle.open_time), func.max(MarketCandle.open_time)).where(
                MarketCandle.pair == symbol,
                MarketCandle.timeframe == timeframe.value,
            )
        )
        return row.one()

    async def get_symbols(self) -> list[str]:
        rows = await self.session.execute(select(distinct(MarketCandle.pair)).order_by(MarketCandle.pair))
        return list(rows.scalars())

    async def get_instrument(self, symbol: str) -> Market | None:
        row = await self.session.get(InstrumentModel, symbol)
        if row is None:
            return None
        metadata = row.metadata_json or {}
        try:
            return Market.model_validate(metadata)
        except ValueError:
            base, _, quote = symbol.removeprefix("B-").partition("_")
            return Market(
                symbol=symbol,
                base_asset=base,
                quote_asset=quote or row.margin_currency,
                market_type=MarketType.FUTURES,
                status=row.status,
            )


class InMemoryHistoricalDataProvider:
    def __init__(self, candles: dict[tuple[str, Timeframe], list[NormalizedCandle]]) -> None:
        self.candles = candles

    async def get_candles(self, symbol, timeframe, start, end):
        return [row for row in self.candles.get((symbol, timeframe), []) if start <= row.timestamp < end]

    async def get_candles_with_warmup(self, symbol, timeframe, start, end, warmup):
        rows = self.candles.get((symbol, timeframe), [])
        prior = [row for row in rows if row.timestamp < start][-warmup:]
        return [*prior, *[row for row in rows if start <= row.timestamp < end]]

    async def get_available_range(self, symbol, timeframe):
        rows = self.candles.get((symbol, timeframe), [])
        return (rows[0].timestamp, rows[-1].timestamp) if rows else (None, None)

    async def get_symbols(self):
        return sorted({symbol for symbol, _ in self.candles})

    async def get_instrument(self, _symbol):
        return None


def candle_close_time(candle: NormalizedCandle) -> datetime:
    return candle.timestamp + TIMEFRAME_DURATION[candle.timeframe]
