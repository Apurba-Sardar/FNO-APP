from math import ceil

import structlog

from app.strategy.models import StrategyStatus

from .config import MissingDataPolicy, RiskConfig
from .daily_limits import daily_loss
from .fees import FeeEstimator
from .models import (
    RiskCheck,
    RiskContext,
    RiskDecision,
    RiskDecisionStatus,
    RiskSeverity,
)
from .position_sizing import PositionSizer, quantity_step
from .slippage import SlippageEstimator
from .validators import structural_rr, valid_stop, valid_target


class RiskEngine:
    """Pure point-in-time risk authority with no API, clock, or execution dependency."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self.fees = FeeEstimator(config)
        self.slippage = SlippageEstimator(config)
        self.sizer = PositionSizer(config)

    def evaluate(self, context: RiskContext) -> RiskDecision:
        checks: list[RiskCheck] = []
        warnings: list[str] = []
        setup = context.strategy_setup
        account = context.account

        def check(name, passed, value, threshold, explanation, severity=RiskSeverity.CRITICAL):
            checks.append(
                RiskCheck(
                    name=name,
                    passed=bool(passed),
                    value=value,
                    threshold=threshold,
                    severity=severity,
                    explanation=explanation,
                )
            )

        equity = account.account_equity
        available = account.available_balance
        check("ACCOUNT_EQUITY", equity is not None and equity > 0, equity, "> 0", "Reliable account equity is mandatory.")
        check("AVAILABLE_BALANCE", available is not None and available > 0, available, "> 0", "Available balance must be positive.")
        account_age = (
            (context.evaluation_timestamp - account.timestamp).total_seconds()
            if account.timestamp is not None
            else None
        )
        check(
            "ACCOUNT_DATA_FRESHNESS",
            account_age is not None
            and 0 <= account_age <= self.config.max_account_data_age_seconds,
            account_age,
            self.config.max_account_data_age_seconds,
            "Account data must be available, not future-dated, and fresh.",
        )
        check("SETUP_STATUS", setup.status == StrategyStatus.TRIGGERED, setup.status.value, "triggered", "Only a closed-candle triggered setup can be risk-approved.")

        _, _, loss_percent = daily_loss(account, self.config)
        check("DAILY_LOSS", loss_percent < self.config.max_daily_loss_percent, loss_percent, self.config.max_daily_loss_percent, "New setups are blocked at the daily loss ceiling.")
        consecutive_blocked = account.consecutive_losses >= self.config.max_consecutive_losses
        if consecutive_blocked and account.consecutive_loss_reset_at is not None:
            consecutive_blocked = context.evaluation_timestamp < account.consecutive_loss_reset_at
        check("CONSECUTIVE_LOSSES", not consecutive_blocked, account.consecutive_losses, self.config.max_consecutive_losses, "Consecutive-loss protection must be clear.")
        confirmed = [position for position in account.open_positions if position.status != "confirmed_closed"]
        check("OPEN_POSITIONS", len(confirmed) < self.config.max_open_positions, len(confirmed), self.config.max_open_positions, "Only confirmed-closed positions release a slot.")
        conflicting = [position for position in confirmed if position.symbol == setup.symbol]
        symbol_exposure_ok = not conflicting or not self.config.one_direction_per_symbol
        check(
            "SYMBOL_EXPOSURE",
            symbol_exposure_ok,
            len(conflicting),
            0 if self.config.one_direction_per_symbol else "not enforced",
            "Duplicate or opposing symbol exposure is disabled when one-direction mode is enabled.",
        )

        entry, stop, target = setup.hypothetical_entry, setup.hypothetical_stop, setup.hypothetical_target
        check("ENTRY_VALIDITY", entry is not None and entry > 0, entry, "> 0", "A positive hypothetical entry is mandatory.")
        stop_ok = entry is not None and stop is not None and valid_stop(setup.direction, entry, stop)
        check("STOP_VALIDITY", stop_ok, stop, "correct side of entry", "Stop must be present and structurally invalidate the direction.")
        target_ok = entry is not None and target is not None and valid_target(setup.direction, entry, target)
        check("TARGET_VALIDITY", target_ok, target, "correct side of entry", "Target must be present and on the rewarding side.")
        rr = structural_rr(entry, stop, target) if entry and stop and target else 0.0
        check("RR", rr >= self.config.minimum_risk_reward, rr, self.config.minimum_risk_reward, "Risk/reward is independently recalculated.")

        atr_distance = abs(entry - stop) / context.atr if entry and stop and context.atr else None
        check("STOP_ATR_DISTANCE", atr_distance is not None and self.config.min_stop_distance_atr <= atr_distance <= self.config.max_stop_distance_atr, atr_distance, [self.config.min_stop_distance_atr, self.config.max_stop_distance_atr], "Stop distance must remain within configured ATR bounds.")
        check("LIQUIDITY", context.liquidity_usable, context.liquidity_usable, True, "Current normalized liquidity must be usable.")
        spread_known = context.spread_percent is not None
        spread_ok = spread_known and context.spread_percent <= self.config.max_spread_percent
        if not spread_known and self.config.missing_spread_policy == MissingDataPolicy.ALLOW_WITH_WARNING:
            spread_ok = True
            warnings.append("spread unavailable; allowed by configured warning policy")
        check("SPREAD", spread_ok, context.spread_percent, self.config.max_spread_percent, "Spread is revalidated at risk-evaluation time.")
        effective_slippage, slippage_warning = self.slippage.effective_percent(context.estimated_slippage_percent)
        if slippage_warning:
            warnings.append(slippage_warning)
        slippage_ok = effective_slippage is not None and effective_slippage <= self.config.max_estimated_slippage_percent
        check("SLIPPAGE", slippage_ok, effective_slippage, self.config.max_estimated_slippage_percent, "Effective slippage includes the configured safety buffer.")

        market_age = (
            (context.evaluation_timestamp - context.market_data_timestamp).total_seconds()
            if context.market_data_timestamp is not None
            else None
        )
        check("MARKET_DATA_FRESHNESS", market_age is not None and 0 <= market_age <= self.config.max_market_data_age_seconds, market_age, self.config.max_market_data_age_seconds, "Market data must be available, not future-dated, and fresh.")
        setup_age = (context.evaluation_timestamp - setup.evaluation_timestamp).total_seconds() / 60
        not_expired = setup.expires_at is None or context.evaluation_timestamp < setup.expires_at
        check("SETUP_AGE", 0 <= setup_age <= self.config.max_setup_age_minutes and not_expired, setup_age, self.config.max_setup_age_minutes, "Stale or expired triggers cannot be approved.")
        drift = abs(context.current_price - entry) / entry * 100 if context.current_price and entry else None
        check("PRICE_DRIFT", drift is not None and drift <= self.config.max_entry_drift_percent, drift, self.config.max_entry_drift_percent, "Current price must remain close to the strategy entry.")

        instrument = context.instrument
        step = quantity_step(instrument)
        market_status = instrument.status.lower() if instrument is not None else None
        check(
            "MARKET_STATUS",
            market_status in {"active", "trading"},
            market_status,
            ["active", "trading"],
            "The normalized instrument must be in an active trading state.",
        )
        check("INSTRUMENT_CONSTRAINTS", instrument is not None and step is not None, None if instrument is None else instrument.symbol, "quantity step available", "Exchange quantity constraints are mandatory.")

        exposure = sum(position.notional for position in confirmed)
        maximum_total = equity * self.config.max_total_exposure_percent / 100 if equity else 0.0
        available_exposure = maximum_total - exposure
        risk_budget = equity * self.config.risk_per_trade_percent / 100 if equity else 0.0

        sizing = None
        if entry and stop and instrument and step and effective_slippage is not None and risk_budget > 0:
            sizing = self.sizer.calculate(
                entry=entry,
                stop=stop,
                risk_budget=risk_budget,
                effective_slippage_percent=effective_slippage,
                instrument=instrument,
                maximum_new_notional=available_exposure,
            )
        quantity = sizing.quantity if sizing else 0.0
        notional = sizing.notional if sizing else 0.0
        minimum_quantity = instrument.min_quantity if instrument else None
        minimum_notional = instrument.min_notional if instrument else None
        check("MINIMUM_QUANTITY", sizing is not None and quantity > 0 and (minimum_quantity is None or quantity >= minimum_quantity), quantity, minimum_quantity, "Rounded-down quantity must satisfy the exchange minimum.")
        check("MINIMUM_NOTIONAL", sizing is not None and (minimum_notional is None or notional >= minimum_notional), notional, minimum_notional, "Risk size must satisfy minimum notional without increasing quantity.")
        check("MAXIMUM_NOTIONAL", notional <= self.config.max_position_notional, notional, self.config.max_position_notional, "Position notional is capped independently of account risk.")
        exposure_after = exposure + notional
        exposure_after_percent = exposure_after / equity * 100 if equity else 0.0
        check("TOTAL_EXPOSURE", equity is not None and exposure_after_percent <= self.config.max_total_exposure_percent, exposure_after_percent, self.config.max_total_exposure_percent, "Total notional exposure must remain within the portfolio ceiling.")

        safe_balance = available * (1 - self.config.margin_safety_buffer_percent / 100) if available else 0.0
        required_leverage = max(1.0, notional / safe_balance) if safe_balance > 0 else float("inf")
        estimated_leverage = ceil(required_leverage * 100) / 100 if required_leverage != float("inf") else 0.0
        check("LEVERAGE", estimated_leverage > 0 and estimated_leverage <= self.config.max_leverage, estimated_leverage, self.config.max_leverage, "Leverage changes margin only and never expands the risk budget.")
        usable_leverage = min(3.0, self.config.max_leverage) if self.config.max_leverage >= 1 else min(estimated_leverage, self.config.max_leverage)
        required_margin = notional / usable_leverage if usable_leverage > 0 else 0.0
        remaining_margin = available - required_margin if available is not None else None
        margin_ok = available is not None and required_margin <= safe_balance
        check("MARGIN", margin_ok, required_margin, safe_balance, "Required margin must fit after the safety buffer.")

        maximum_loss = sizing.maximum_loss if sizing else 0.0
        check("MAXIMUM_LOSS", sizing is not None and maximum_loss <= risk_budget + 1e-9, maximum_loss, risk_budget, "Stop risk, fees, and slippage must fit the risk budget.")
        correlated = any(position.correlation_group == context.correlation_group for position in confirmed)
        if correlated:
            warnings.append("correlated exposure exists in the same broad group")

        failed = [item for item in checks if not item.passed and item.severity == RiskSeverity.CRITICAL]
        account_missing = any(
            not item.passed
            for item in checks
            if item.name in {"ACCOUNT_EQUITY", "AVAILABLE_BALANCE", "ACCOUNT_DATA_FRESHNESS"}
        )
        market_missing = not next(item for item in checks if item.name == "MARKET_DATA_FRESHNESS").passed
        limit_names = {"DAILY_LOSS", "CONSECUTIVE_LOSSES", "OPEN_POSITIONS", "SYMBOL_EXPOSURE", "TOTAL_EXPOSURE"}
        limit_reached = any(item.name in limit_names for item in failed)
        allowed = not failed
        status = (
            RiskDecisionStatus.ACCOUNT_DATA_UNAVAILABLE
            if account_missing
            else RiskDecisionStatus.MARKET_DATA_UNAVAILABLE
            if market_missing
            else RiskDecisionStatus.RISK_LIMIT_REACHED
            if limit_reached
            else RiskDecisionStatus.REJECTED
            if failed
            else RiskDecisionStatus.WARNING
            if warnings
            else RiskDecisionStatus.APPROVED
        )
        reward = abs(target - entry) * quantity if entry and target else 0.0
        decision = RiskDecision(
            symbol=setup.symbol,
            strategy=setup.strategy,
            direction=setup.direction,
            allowed=allowed,
            status=status,
            evaluation_timestamp=context.evaluation_timestamp,
            risk_amount=risk_budget,
            risk_percent=self.config.risk_per_trade_percent if equity else 0,
            position_quantity=quantity,
            position_notional=notional,
            estimated_leverage=estimated_leverage,
            required_margin=required_margin,
            remaining_available_margin=remaining_margin,
            estimated_fees=sizing.fees if sizing else 0,
            estimated_slippage_cost=sizing.slippage if sizing else 0,
            stop_loss_risk=sizing.stop_risk if sizing else 0,
            maximum_loss=maximum_loss,
            estimated_reward=reward,
            estimated_rr=rr,
            entry_drift_percent=drift,
            exposure_percent_after=exposure_after_percent,
            correlated_exposure_warning=correlated,
            maximum_trade_duration_minutes=self.config.max_trade_duration_minutes,
            warnings=warnings,
            rejection_reasons=[item.explanation for item in failed],
            checks=checks,
        )
        self._log(decision)
        return decision

    @staticmethod
    def _log(decision: RiskDecision) -> None:
        values = {
            "symbol": decision.symbol,
            "strategy": decision.strategy.value,
            "risk_status": decision.status.value,
            "risk_budget": decision.risk_amount,
            "maximum_loss": decision.maximum_loss,
            "timestamp": decision.evaluation_timestamp.isoformat(),
        }
        logger = structlog.get_logger()
        logger.info("RISK_EVALUATION", **values)
        logger.info("RISK_APPROVED" if decision.allowed else "RISK_REJECTED", **values)
        if decision.status == RiskDecisionStatus.RISK_LIMIT_REACHED:
            logger.warning("RISK_LIMIT_REACHED", **values)
        if decision.status in {RiskDecisionStatus.ACCOUNT_DATA_UNAVAILABLE, RiskDecisionStatus.MARKET_DATA_UNAVAILABLE}:
            logger.warning("RISK_DATA_UNAVAILABLE", **values)
