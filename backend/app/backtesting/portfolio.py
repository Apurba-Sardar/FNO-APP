from collections import defaultdict
from datetime import datetime
from uuid import UUID, uuid4

from app.risk.models import AccountSnapshot, OpenPosition

from .models import BacktestPosition, BacktestTrade, EquityPoint


class BacktestPortfolio:
    def __init__(self, initial_equity: float) -> None:
        self.initial_equity = initial_equity
        self.equity = initial_equity
        self.peak_equity = initial_equity
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_funding = 0.0
        self.open_positions: dict[str, BacktestPosition] = {}
        self.trades: list[BacktestTrade] = []
        self.equity_curve: list[EquityPoint] = []
        self.daily_pnl: dict[str, float] = defaultdict(float)
        self.consecutive_losses = 0
        self.last_prices: dict[str, float] = {}

    @property
    def unrealized_pnl(self) -> float:
        total = 0.0
        for symbol, position in self.open_positions.items():
            price = self.last_prices.get(symbol, position.entry_price)
            sign = 1 if position.direction.value == "long" else -1
            total += (price - position.entry_price) * position.quantity * sign
        return total

    @property
    def account_equity(self) -> float:
        return self.equity + self.unrealized_pnl

    @property
    def exposure(self) -> float:
        return sum(item.notional for item in self.open_positions.values())

    @property
    def available_margin(self) -> float:
        used = sum(item.notional / max(item.leverage, 1) for item in self.open_positions.values())
        return max(0.0, self.account_equity - used)

    def update_mark(self, symbol: str, price: float) -> None:
        self.last_prices[symbol] = price

    def account_snapshot(self, timestamp: datetime) -> AccountSnapshot:
        key = timestamp.date().isoformat()
        return AccountSnapshot(
            account_equity=max(self.account_equity, 1e-9),
            available_balance=self.available_margin,
            starting_day_equity=max(self.equity - self.daily_pnl[key], 1e-9),
            realized_pnl_today=self.daily_pnl[key],
            unrealized_pnl=self.unrealized_pnl,
            fees_today=0,
            funding_today=0,
            consecutive_losses=self.consecutive_losses,
            open_positions=[
                OpenPosition(
                    symbol=item.symbol,
                    direction=item.direction,
                    notional=item.notional,
                )
                for item in self.open_positions.values()
            ],
            timestamp=timestamp,
        )

    def add(self, position: BacktestPosition) -> bool:
        if position.symbol in self.open_positions:
            return False
        self.open_positions[position.symbol] = position
        return True

    def record_close(self, backtest_id: UUID, position: BacktestPosition, strategy_version: str):
        self.open_positions.pop(position.symbol, None)
        self.realized_pnl += position.net_pnl
        self.equity += position.net_pnl
        self.total_fees += position.fees
        self.total_funding += position.funding_cost
        self.daily_pnl[position.exit_timestamp.date().isoformat()] += position.net_pnl
        self.consecutive_losses = self.consecutive_losses + 1 if position.net_pnl < 0 else 0
        trade = BacktestTrade(
            trade_id=uuid4(),
            backtest_id=backtest_id,
            symbol=position.symbol,
            strategy=position.strategy,
            direction=position.direction,
            setup_score=position.setup_score,
            opportunity_score=position.opportunity_score,
            entry=position.entry_price,
            stop=position.stop,
            target=position.target,
            exit=position.exit_price,
            quantity=position.quantity,
            notional=position.notional,
            leverage=position.leverage,
            entry_time=position.entry_timestamp,
            exit_time=position.exit_timestamp,
            exit_reason=position.exit_reason,
            gross_pnl=position.gross_pnl,
            fees=position.fees,
            slippage=position.slippage_cost,
            funding=position.funding_cost,
            net_pnl=position.net_pnl,
            r_multiple=position.r_multiple,
            duration_minutes=(position.exit_timestamp - position.entry_timestamp).total_seconds() / 60,
            maximum_favorable_excursion=position.maximum_favorable_excursion,
            maximum_adverse_excursion=position.maximum_adverse_excursion,
            market_regime=position.market_regime,
            factor_snapshot=position.factor_snapshot,
            strategy_version=strategy_version,
            risk_decision=position.risk_decision,
            lifecycle=position.lifecycle,
        )
        self.trades.append(trade)
        return trade

    def mark(self, timestamp: datetime) -> EquityPoint:
        equity = self.account_equity
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = self.peak_equity - equity
        point = EquityPoint(
            timestamp=timestamp,
            equity=equity,
            drawdown=drawdown,
            drawdown_percent=drawdown / self.peak_equity * 100 if self.peak_equity else 0,
            daily_pnl=self.daily_pnl[timestamp.date().isoformat()],
        )
        self.equity_curve.append(point)
        return point
