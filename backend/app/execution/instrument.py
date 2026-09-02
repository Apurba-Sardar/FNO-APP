from decimal import ROUND_DOWN, Decimal

from app.market_data.models import Market


class InstrumentMapper:
    @staticmethod
    def exchange_pair(internal_symbol: str, market: Market) -> str:
        pair = market.symbol
        normalized_internal = internal_symbol.removeprefix("B-")
        if pair.removeprefix("B-") != normalized_internal:
            raise ValueError("internal symbol does not match CoinDCX instrument metadata")
        if not pair.startswith("B-") or market.quote_asset != "USDT":
            raise ValueError("instrument is not a documented USDT futures pair")
        if market.status.lower() != "active":
            raise ValueError("instrument is not active")
        return pair

    @staticmethod
    def floor_quantity(quantity: float, market: Market) -> float:
        if market.step_size is None or market.step_size <= 0:
            raise ValueError("quantity increment is unavailable")
        step = Decimal(str(market.step_size))
        value = (Decimal(str(quantity)) / step).to_integral_value(rounding=ROUND_DOWN) * step
        result = float(value)
        if result <= 0 or (market.min_quantity is not None and result < market.min_quantity):
            raise ValueError("quantity is below the instrument minimum")
        return result
