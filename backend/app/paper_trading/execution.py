from datetime import datetime
from uuid import UUID

import structlog

from app.execution.interface import TradeExecutor
from app.risk.models import RiskDecision
from app.strategy.models import StrategyDirection, StrategyResult, StrategyStatus

from .config import PaperExecutionModel, PaperMarkPrice, PaperTradingConfig
from .exceptions import PaperConfigurationError, PaperExecutionRejected, StaleMarketData
from .fees import paper_fee_model
from .funding import PaperFundingModel
from .models import (
    ExecutionMode,
    MarketQuote,
    PaperExitReason,
    PaperOrder,
    PaperOrderStatus,
    PaperPosition,
    PaperPositionStatus,
    PaperState,
    PaperTrade,
)
from .portfolio import refresh_account
from .slippage import paper_slippage_model


class PaperTradeExecutor(TradeExecutor):
    """Pure simulator. It intentionally cannot receive an exchange/private client."""

    def __init__(self, config: PaperTradingConfig, taker_fee_percent: float, *, mode="paper"):
        if mode != ExecutionMode.PAPER and mode != "paper":
            raise PaperConfigurationError("PaperTradeExecutor only supports PAPER mode")
        self.config = config
        self.mode = ExecutionMode.PAPER
        self.fees = paper_fee_model(taker_fee_percent)
        self.slippage = paper_slippage_model(
            config.entry_slippage_bps, config.exit_slippage_bps
        )
        self.funding = PaperFundingModel(config.funding_enabled)

    def _base_price(self, quote: MarketQuote, direction: StrategyDirection, entry: bool) -> float:
        model = self.config.execution_model
        if model == PaperExecutionModel.MID_PRICE:
            price = quote.mid
        elif model == PaperExecutionModel.LAST_PRICE:
            price = quote.last
        elif entry:
            price = quote.ask if direction == StrategyDirection.LONG else quote.bid
        else:
            price = quote.bid if direction == StrategyDirection.LONG else quote.ask
        if price is None:
            raise PaperExecutionRejected("required bid/ask market price is unavailable")
        return price

    def validate_quote(self, quote: MarketQuote, now: datetime) -> None:
        age = (now - quote.timestamp).total_seconds()
        if age < 0 or age > self.config.max_stale_seconds:
            raise StaleMarketData(f"market quote is stale ({age:.1f}s)")

    def execute_entry(
        self,
        state: PaperState,
        setup: StrategyResult,
        decision: RiskDecision,
        quote: MarketQuote,
        now: datetime,
        setup_id: str,
        *,
        market_regime: str = "unknown",
        factor_snapshot: dict | None = None,
    ) -> PaperPosition:
        self.validate_quote(quote, now)
        if setup.status != StrategyStatus.TRIGGERED or not decision.allowed:
            raise PaperExecutionRejected("entry requires TRIGGERED setup and APPROVED Phase 7 risk")
        if decision.position_quantity <= 0:
            raise PaperExecutionRejected("risk-approved quantity must be positive")
        if any(item.setup_id == setup_id and item.status == PaperOrderStatus.FILLED for item in state.orders):
            raise PaperExecutionRejected("duplicate setup")
        if any(item.symbol == setup.symbol and item.status == PaperPositionStatus.OPEN for item in state.positions):
            raise PaperExecutionRejected("symbol already has an open position")
        cooldown = state.cooldowns.get(setup.symbol)
        if cooldown and now < cooldown:
            raise PaperExecutionRejected("symbol cooldown active")
        if setup.hypothetical_stop is None or setup.hypothetical_target is None:
            raise PaperExecutionRejected("stop and target are mandatory")

        requested = self._base_price(quote, setup.direction, True)
        executed = self.slippage.price(requested, setup.direction, entry=True)
        theoretical = setup.hypothetical_entry or requested
        drift = abs(executed - theoretical) / theoretical * 100
        max_drift = next(
            (check.threshold for check in decision.checks if check.name == "PRICE_DRIFT"),
            None,
        )
        if isinstance(max_drift, (float, int)) and drift > max_drift:
            raise PaperExecutionRejected("simulated fill exceeds Phase 7 entry-drift limit")
        quantity = decision.position_quantity
        fee = self.fees.estimate(executed, quantity)
        slippage = abs(executed - requested) * quantity
        order = PaperOrder(
            symbol=setup.symbol,
            direction=setup.direction,
            quantity=quantity,
            requested_price=requested,
            executed_price=executed,
            status=PaperOrderStatus.FILLED,
            created_at=now,
            executed_at=now,
            strategy=setup.strategy,
            setup_id=setup_id,
            opportunity_score=setup.opportunity_score,
            setup_score=setup.setup_quality_score,
            fees=fee,
            slippage=slippage,
            idempotency_key=setup_id,
            lifecycle=["intent_created", "validating", "submitting", "filled"],
        )
        position = PaperPosition(
            order_id=order.order_id,
            setup_id=setup_id,
            symbol=setup.symbol,
            direction=setup.direction,
            strategy=setup.strategy,
            quantity=quantity,
            entry_price=executed,
            entry_timestamp=now,
            stop_price=setup.hypothetical_stop,
            target_price=setup.hypothetical_target,
            current_price=executed,
            entry_fee=fee,
            slippage=slippage,
            funding_status=self.funding.status,
            initial_trade_risk=max(decision.maximum_loss, 0.00000001),
            leverage=max(decision.estimated_leverage, 1),
            opportunity_score=setup.opportunity_score,
            setup_score=setup.setup_quality_score,
            market_regime=market_regime,
            factor_snapshot=factor_snapshot or {},
            protection_status="protected",
            protection_lifecycle=["protection_pending", "stop_created", "target_created", "protected"],
        )
        position.factor_snapshot["requested_entry"] = requested
        position.factor_snapshot["entry_slippage"] = slippage
        state.orders.append(order)
        structlog.get_logger().info(
            "PAPER_ORDER_CREATED", symbol=setup.symbol, strategy=setup.strategy.value,
            setup_id=setup_id, timestamp=now.isoformat()
        )
        structlog.get_logger().info(
            "PAPER_ORDER_FILLED", symbol=setup.symbol, strategy=setup.strategy.value,
            setup_id=setup_id, timestamp=now.isoformat()
        )
        state.positions.append(position)
        # Internal protective orders, never exchange orders.
        for kind, price in (("paper_stop", position.stop_price), ("paper_target", position.target_price)):
            state.orders.append(PaperOrder(
                symbol=setup.symbol,
                direction=setup.direction,
                order_type=kind,
                quantity=quantity,
                requested_price=price,
                status=PaperOrderStatus.PENDING,
                created_at=now,
                strategy=setup.strategy,
                setup_id=setup_id,
                opportunity_score=setup.opportunity_score,
                setup_score=setup.setup_quality_score,
                idempotency_key=f"{setup_id}:{kind}",
                lifecycle=["intent_created", "validating", "pending"],
            ))
        state.account.fees += fee
        state.account.slippage_cost += slippage
        state.counters.entries += 1
        refresh_account(state, now)
        structlog.get_logger().info(
            "PAPER_POSITION_OPENED", symbol=setup.symbol, strategy=setup.strategy.value,
            setup_id=setup_id, position_id=str(position.position_id), timestamp=now.isoformat()
        )
        return position

    def mark(self, position: PaperPosition, quote: MarketQuote) -> None:
        if self.config.position_mark_price == PaperMarkPrice.MID_PRICE:
            price = quote.mid
        elif self.config.position_mark_price == PaperMarkPrice.LAST_PRICE:
            price = quote.last
        else:
            price = self._base_price(quote, position.direction, False)
        if price is None:
            raise PaperExecutionRejected("configured paper mark price is unavailable")
        position.current_price = price
        multiplier = 1 if position.direction == StrategyDirection.LONG else -1
        position.unrealized_pnl = (price - position.entry_price) * position.quantity * multiplier
        position.maximum_favorable_excursion = max(
            position.maximum_favorable_excursion, position.unrealized_pnl
        )
        position.maximum_adverse_excursion = max(
            position.maximum_adverse_excursion, -position.unrealized_pnl
        )

    def trigger_reason(self, position: PaperPosition, quote: MarketQuote, now: datetime, max_minutes: int):
        self.mark(position, quote)
        long = position.direction == StrategyDirection.LONG
        if (long and position.current_price <= position.stop_price) or (
            not long and position.current_price >= position.stop_price
        ):
            return PaperExitReason.STOP_LOSS
        if (long and position.current_price >= position.target_price) or (
            not long and position.current_price <= position.target_price
        ):
            return PaperExitReason.TAKE_PROFIT
        if (now - position.entry_timestamp).total_seconds() >= max_minutes * 60:
            return PaperExitReason.TIME_EXIT
        return None

    @staticmethod
    def candle_trigger_reason(position: PaperPosition, high: float, low: float):
        """Conservative fallback when no tick ordering exists: stop always wins ambiguity."""
        long = position.direction == StrategyDirection.LONG
        stop_hit = low <= position.stop_price if long else high >= position.stop_price
        target_hit = high >= position.target_price if long else low <= position.target_price
        if stop_hit:
            return PaperExitReason.STOP_LOSS
        if target_hit:
            return PaperExitReason.TAKE_PROFIT
        return None

    def execute_exit(
        self,
        state: PaperState,
        position: PaperPosition,
        quote: MarketQuote,
        reason: PaperExitReason,
        now: datetime,
        session_id: UUID,
        strategy_version: str,
        risk_version: str,
    ) -> PaperTrade:
        self.validate_quote(quote, now)
        if position.status != PaperPositionStatus.OPEN:
            raise PaperExecutionRejected("position is not open")
        requested = self._base_price(quote, position.direction, False)
        executed = self.slippage.price(requested, position.direction, entry=False)
        multiplier = 1 if position.direction == StrategyDirection.LONG else -1
        gross = (executed - position.entry_price) * position.quantity * multiplier
        exit_fee = self.fees.estimate(executed, position.quantity)
        exit_slippage = abs(executed - requested) * position.quantity
        net = gross - position.entry_fee - exit_fee - position.funding
        position.status = PaperPositionStatus.CLOSED
        position.exit_price = executed
        position.exit_timestamp = now
        position.exit_reason = reason
        position.realized_pnl = net
        position.unrealized_pnl = 0
        position.exit_fee = exit_fee
        position.slippage += exit_slippage
        for order in state.orders:
            if order.setup_id == position.setup_id and order.status == PaperOrderStatus.PENDING:
                order.status = PaperOrderStatus.FILLED if (
                    (reason == PaperExitReason.STOP_LOSS and order.order_type == "paper_stop")
                    or (reason == PaperExitReason.TAKE_PROFIT and order.order_type == "paper_target")
                ) else PaperOrderStatus.CANCELLED
        trade = PaperTrade(
            session_id=session_id, position_id=position.position_id, symbol=position.symbol,
            strategy=position.strategy, direction=position.direction,
            opportunity_score=position.opportunity_score, setup_score=position.setup_score,
            entry=position.entry_price, stop=position.stop_price, target=position.target_price,
            quantity=position.quantity, notional=position.notional,
            entry_fee=position.entry_fee, exit_fee=exit_fee,
            fees=position.entry_fee + exit_fee, slippage=position.slippage,
            funding=position.funding, funding_status=position.funding_status,
            exit=executed, exit_reason=reason, gross_pnl=gross, net_pnl=net,
            r_multiple=net / position.initial_trade_risk,
            duration_minutes=(now - position.entry_timestamp).total_seconds() / 60,
            maximum_favorable_excursion=position.maximum_favorable_excursion,
            maximum_adverse_excursion=position.maximum_adverse_excursion,
            market_regime=position.market_regime, factor_snapshot=position.factor_snapshot,
            strategy_version=strategy_version, risk_version=risk_version, timestamp=now,
            evaluation_time=position.factor_snapshot.get("evaluation_time"),
            entry_time=position.entry_timestamp,
            exit_time=now,
            planned_entry=position.factor_snapshot.get("planned_entry"),
            risk_amount=position.factor_snapshot.get("risk_amount"),
            risk_percent=position.factor_snapshot.get("risk_percent"),
            risk_decision=position.factor_snapshot.get("risk_decision", {}),
            strategy_explanation=position.factor_snapshot.get("strategy_explanation", []),
            market_context=position.factor_snapshot.get("market_context", {}),
            order_lifecycle=position.factor_snapshot.get(
                "order_lifecycle", ["intent_created", "validating", "submitting", "filled"]
            ),
            protection_lifecycle=position.protection_lifecycle,
            data_quality=position.factor_snapshot.get("data_quality", {}),
            execution_quality={
                "requested_entry": position.factor_snapshot.get("requested_entry"),
                "actual_entry": position.entry_price,
                "actual_exit": executed,
                "entry_slippage": position.factor_snapshot.get("entry_slippage", 0),
                "total_slippage": position.slippage,
                "fees": position.entry_fee + exit_fee,
            },
        )
        state.trades.append(trade)
        state.account.realized_pnl += net
        state.account.daily_pnl += net
        state.account.fees += exit_fee
        state.account.slippage_cost += exit_slippage
        state.account.consecutive_losses = state.account.consecutive_losses + 1 if net < 0 else 0
        state.counters.exits += 1
        refresh_account(state, now)
        structlog.get_logger().info(
            "PAPER_POSITION_CLOSED", symbol=position.symbol, strategy=position.strategy.value,
            setup_id=position.setup_id, position_id=str(position.position_id),
            reason=reason.value, timestamp=now.isoformat()
        )
        return trade

    def cancel_order(self, order: PaperOrder) -> PaperOrder:
        if order.status in {PaperOrderStatus.CREATED, PaperOrderStatus.PENDING}:
            order.status = PaperOrderStatus.CANCELLED
        return order
