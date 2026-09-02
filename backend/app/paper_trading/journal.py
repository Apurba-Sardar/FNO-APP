from .models import PaperState, PaperTrade


class PaperTradeJournal:
    @staticmethod
    def append(state: PaperState, trade: PaperTrade) -> None:
        if not any(item.trade_id == trade.trade_id for item in state.trades):
            state.trades.append(trade)
