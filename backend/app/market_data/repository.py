from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InstrumentModel, MarketCandle

from .models import NormalizedCandle


class CandleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, candles: list[NormalizedCandle]) -> int:
        if not candles:
            return 0
        symbols = sorted({item.symbol for item in candles})
        instrument_rows = [
            {"pair": symbol, "status": "active", "margin_currency": "USDT", "metadata_json": {}}
            for symbol in symbols
        ]
        await self.session.execute(
            insert(InstrumentModel)
            .values(instrument_rows)
            .on_conflict_do_nothing(index_elements=[InstrumentModel.pair])
        )
        rows = [
            {
                "pair": item.symbol,
                "timeframe": item.timeframe.value,
                "open_time": item.timestamp,
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "volume": item.volume,
            }
            for item in candles
        ]
        result = await self.session.execute(
            insert(MarketCandle)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    MarketCandle.pair,
                    MarketCandle.timeframe,
                    MarketCandle.open_time,
                ]
            )
        )
        await self.session.commit()
        return result.rowcount or 0
