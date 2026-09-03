from dataclasses import dataclass
from typing import Any

from app.market_data.models import Market
from app.risk.models import RiskDecision
from app.strategy.models import StrategyDirection, StrategyResult

from .instrument import InstrumentMapper


@dataclass(frozen=True)
class BuiltOrder:
    payload: dict[str, Any]
    quantity: float
    pair: str


class CoinDCXOrderRequestBuilder:
    """Server-side conversion only; browser values never enter this builder."""

    def build_market(
        self,
        setup: StrategyResult,
        decision: RiskDecision,
        market: Market,
        *,
        margin_mode: str = "isolated",
    ) -> BuiltOrder:
        if not decision.allowed or setup.direction not in {StrategyDirection.LONG, StrategyDirection.SHORT}:
            raise ValueError("setup and risk decision do not authorize an entry")
        pair = InstrumentMapper.exchange_pair(setup.symbol, market)
        quantity = InstrumentMapper.floor_quantity(decision.position_quantity, market)
        payload = {
            "order": {
                "side": "buy" if setup.direction == StrategyDirection.LONG else "sell",
                "pair": pair,
                "order_type": "market_order",
                "total_quantity": quantity,
                "leverage": int(decision.estimated_leverage),
                "notification": "no_notification",
                "hidden": False,
                "post_only": False,
                "margin_currency_short_name": "USDT",
                "position_margin_type": margin_mode,
            }
        }
        return BuiltOrder(payload=payload, quantity=quantity, pair=pair)
