from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.market_data.models import NormalizedCandle
from app.risk.models import RiskDecision
from app.strategy.models import StrategyDirection, StrategyResult

from .config import BacktestConfig, ExecutionModel, IntrabarPolicy, SlippageModelKind
from .models import BacktestPosition, ExitReason, LifecycleEvent, PositionState


class FeeModel:
    def __init__(self, config) -> None:
        self.config = config

    @property
    def rate(self) -> float:
        value = self.config.taker_fee_percent if self.config.use_taker else self.config.maker_fee_percent
        return value / 100

    def estimate(self, price: float, quantity: float) -> float:
        return price * quantity * self.rate


class SlippageModel:
    def __init__(self, config) -> None:
        self.config = config

    def bps(self, *, entry: bool, atr_percent: float | None = None) -> float:
        base = self.config.entry_slippage_bps if entry else self.config.exit_slippage_bps
        if self.config.kind == SlippageModelKind.VOLATILITY_ADJUSTED:
            return base * (1 + (atr_percent or 0) / 100 * self.config.volatility_multiplier)
        # Historical order-book estimates are intentionally not fabricated.
        return base

    def price(self, price: float, direction: StrategyDirection, *, entry: bool, atr_percent=None):
        adverse = 1 if (direction == StrategyDirection.LONG) == entry else -1
        return price * (1 + adverse * self.bps(entry=entry, atr_percent=atr_percent) / 10_000)


class FundingModel:
    included = False

    def cost(self, *_args, **_kwargs) -> float:
        return 0.0


@dataclass(frozen=True)
class ExitFill:
    reason: ExitReason
    theoretical_price: float


class SimulatedExecutionEngine:
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        self.fees = FeeModel(config.fee_model)
        self.slippage = SlippageModel(config.slippage_model)
        self.funding = FundingModel()

    def enter(
        self,
        setup: StrategyResult,
        decision: RiskDecision,
        candle: NormalizedCandle,
        backtest_id: UUID,
        factor_snapshot: dict,
        market_regime: str,
    ) -> BacktestPosition | None:
        if not decision.allowed or decision.position_quantity <= 0:
            return None
        theoretical = setup.hypothetical_entry
        if theoretical is None or setup.hypothetical_stop is None or setup.hypothetical_target is None:
            return None
        if self.config.execution_model == ExecutionModel.LIMIT:
            touched = candle.low <= theoretical <= candle.high
            if not touched:
                return None
            raw_price = theoretical
        elif self.config.execution_model == ExecutionModel.BREAKOUT_TRIGGER:
            if setup.direction == StrategyDirection.LONG and candle.high < theoretical:
                return None
            if setup.direction == StrategyDirection.SHORT and candle.low > theoretical:
                return None
            raw_price = max(candle.open, theoretical) if setup.direction == StrategyDirection.LONG else min(candle.open, theoretical)
        else:
            raw_price = candle.open
        drift = abs(raw_price - theoretical) / theoretical * 100
        if drift > self.config.risk.max_entry_drift_percent:
            return None
        entry_price = self.slippage.price(raw_price, setup.direction, entry=True)
        quantity = decision.position_quantity
        entry_slippage = abs(entry_price - raw_price) * quantity
        entry_fee = self.fees.estimate(entry_price, quantity)
        stop_fill = self.slippage.price(setup.hypothetical_stop, setup.direction, entry=False)
        stop_fee = self.fees.estimate(stop_fill, quantity)
        actual_maximum_loss = abs(entry_price - stop_fill) * quantity + entry_fee + stop_fee
        if actual_maximum_loss > decision.risk_amount + 1e-9:
            return None
        return BacktestPosition(
            position_id=uuid4(),
            symbol=setup.symbol,
            direction=setup.direction,
            strategy=setup.strategy,
            entry_timestamp=candle.timestamp,
            entry_price=entry_price,
            theoretical_entry=theoretical,
            quantity=quantity,
            notional=entry_price * quantity,
            leverage=decision.estimated_leverage,
            stop=setup.hypothetical_stop,
            target=setup.hypothetical_target,
            initial_risk=actual_maximum_loss,
            fees=entry_fee,
            slippage_cost=entry_slippage,
            opportunity_score=setup.opportunity_score,
            setup_score=setup.setup_quality_score,
            market_regime=market_regime,
            factor_snapshot=factor_snapshot,
            risk_decision=decision,
            lifecycle=[
                LifecycleEvent(timestamp=setup.evaluation_timestamp, state="setup", detail="closed-candle trigger"),
                LifecycleEvent(timestamp=decision.evaluation_timestamp, state="risk_check", detail=decision.status.value),
                LifecycleEvent(timestamp=candle.timestamp, state="entry_attempt", detail=self.config.execution_model.value),
                LifecycleEvent(timestamp=candle.timestamp, state="filled", detail="simulated fill"),
                LifecycleEvent(timestamp=candle.timestamp, state="active", detail="position active"),
            ],
        )

    def exit_trigger(self, position: BacktestPosition, candle: NormalizedCandle, now: datetime):
        long = position.direction == StrategyDirection.LONG
        stop_hit = candle.low <= position.stop if long else candle.high >= position.stop
        target_hit = candle.high >= position.target if long else candle.low <= position.target
        if stop_hit and target_hit:
            return ExitFill(
                ExitReason.STOP_LOSS
                if self.config.intrabar_policy == IntrabarPolicy.ASSUME_STOP_FIRST
                else ExitReason.TAKE_PROFIT,
                position.stop
                if self.config.intrabar_policy == IntrabarPolicy.ASSUME_STOP_FIRST
                else position.target,
            )
        if stop_hit:
            # Gap through a stop is filled at the worse candle open.
            price = min(candle.open, position.stop) if long else max(candle.open, position.stop)
            return ExitFill(ExitReason.STOP_LOSS, price)
        if target_hit:
            return ExitFill(ExitReason.TAKE_PROFIT, position.target)
        age = (now - position.entry_timestamp).total_seconds() / 60
        if age >= self.config.max_trade_duration_minutes:
            return ExitFill(ExitReason.TIME_EXIT, candle.close)
        return None

    def close(self, position: BacktestPosition, fill: ExitFill, timestamp: datetime) -> BacktestPosition:
        exit_price = self.slippage.price(fill.theoretical_price, position.direction, entry=False)
        exit_fee = self.fees.estimate(exit_price, position.quantity)
        exit_slippage = abs(exit_price - fill.theoretical_price) * position.quantity
        sign = 1 if position.direction == StrategyDirection.LONG else -1
        gross = (exit_price - position.entry_price) * position.quantity * sign
        fees = position.fees + exit_fee
        slippage = position.slippage_cost + exit_slippage
        funding = self.funding.cost(position, timestamp)
        net = gross - fees - funding
        return position.model_copy(
            update={
                "state": PositionState.CLOSED,
                "exit_timestamp": timestamp,
                "exit_price": exit_price,
                "exit_reason": fill.reason,
                "gross_pnl": gross,
                "fees": fees,
                "slippage_cost": slippage,
                "funding_cost": funding,
                "net_pnl": net,
                "r_multiple": net / position.initial_risk if position.initial_risk else 0,
                "lifecycle": [
                    *position.lifecycle,
                    LifecycleEvent(timestamp=timestamp, state="closed", detail=fill.reason.value),
                ],
            }
        )

    @staticmethod
    def update_excursions(position: BacktestPosition, candle: NormalizedCandle) -> BacktestPosition:
        sign = 1 if position.direction == StrategyDirection.LONG else -1
        favorable = max(
            0,
            (candle.high - position.entry_price) * position.quantity * sign
            if sign > 0
            else (position.entry_price - candle.low) * position.quantity,
        )
        adverse = max(
            0,
            (position.entry_price - candle.low) * position.quantity
            if sign > 0
            else (candle.high - position.entry_price) * position.quantity,
        )
        return position.model_copy(
            update={
                "maximum_favorable_excursion": max(position.maximum_favorable_excursion, favorable),
                "maximum_adverse_excursion": max(position.maximum_adverse_excursion, adverse),
            }
        )
