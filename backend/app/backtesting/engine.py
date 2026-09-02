from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

import structlog

from app.domain.market import Timeframe
from app.indicators import IndicatorEngine
from app.market_data.normalization import TIMEFRAME_DURATION
from app.risk.engine import RiskEngine
from app.risk.models import RiskContext
from app.scoring.engine import OpportunityScoringEngine
from app.strategy.context import StrategyContextBuilder
from app.strategy.engine import StrategyEngine
from app.strategy.models import StrategyStatus

from .config import BacktestConfig, MissingCandlePolicy
from .context import HistoricalMarketContext
from .execution import ExitFill, SimulatedExecutionEngine
from .historical import HistoricalCandidateBuilder
from .metrics import (
    execution_metrics,
    grouped,
    performance,
    period_metrics,
    r_distribution,
    score_bucket,
)
from .models import (
    BacktestCounters,
    BacktestResult,
    BacktestStatus,
    ExitReason,
)
from .portfolio import BacktestPortfolio
from .validation import validate_historical_data


class BacktestEngine:
    """Chronological runner reusing Phase 5 scoring, Phase 6 strategy, and Phase 7 risk."""

    def __init__(self, provider) -> None:
        self.provider = provider

    async def run(self, config: BacktestConfig, backtest_id: UUID | None = None) -> BacktestResult:
        identifier = backtest_id or uuid4()
        created = datetime.now(UTC)
        result = BacktestResult(
            backtest_id=identifier,
            status=BacktestStatus.RUNNING,
            configuration=config,
            created_at=created,
            started_at=created,
        )
        started = perf_counter()
        try:
            config = await self._resolve_instruments(config)
            result.configuration = config
            data = await self._load(config)
            quality = validate_historical_data(data, config.warmup_candles)
            result.data_quality = quality
            if not quality.valid:
                raise ValueError("historical data contains invalid or duplicate candles")
            if config.missing_candle_policy == MissingCandlePolicy.ABORT_SYMBOL and quality.missing_periods:
                raise ValueError("missing candle policy aborted the backtest")
            portfolio = BacktestPortfolio(config.initial_equity)
            execution = SimulatedExecutionEngine(config)
            scoring = OpportunityScoringEngine(config.scoring)
            strategy = StrategyEngine(
                StrategyContextBuilder(IndicatorEngine(), config.strategy), config.strategy
            )
            risk_config = config.risk.model_copy(
                update={
                    "maker_fee_percent": config.fee_model.maker_fee_percent,
                    "taker_fee_percent": config.fee_model.taker_fee_percent,
                    "fee_mode": "taker" if config.fee_model.use_taker else "maker",
                    "max_trade_duration_minutes": config.max_trade_duration_minutes,
                }
            )
            risk = RiskEngine(risk_config)
            builder = HistoricalCandidateBuilder(config)
            counters = BacktestCounters()
            pending = {}
            events = self._events(data, config)
            last_candles = {}
            for timestamp, symbol, candle in events:
                counters.periods_evaluated += 1
                last_candles[symbol] = candle
                portfolio.update_mark(symbol, candle.close)
                existing = portfolio.open_positions.get(symbol)
                if existing:
                    existing = execution.update_excursions(existing, candle)
                    portfolio.open_positions[symbol] = existing
                    fill = execution.exit_trigger(existing, candle, timestamp)
                    if fill:
                        closed = execution.close(existing, fill, timestamp)
                        portfolio.record_close(identifier, closed, config.strategy_version)
                        counters.exits += 1

                queued = pending.pop(symbol, None)
                if queued and symbol not in portfolio.open_positions:
                    setup, decision, factors, regime, delay = queued
                    if delay > 1:
                        pending[symbol] = (setup, decision, factors, regime, delay - 1)
                    else:
                        counters.entry_attempts += 1
                        position = execution.enter(
                            setup, decision, candle, identifier, factors, regime
                        )
                        if position and portfolio.add(position):
                            counters.entries_filled += 1
                            position = execution.update_excursions(position, candle)
                            portfolio.open_positions[symbol] = position
                            fill = execution.exit_trigger(position, candle, timestamp)
                            if fill:
                                closed = execution.close(position, fill, timestamp)
                                portfolio.record_close(
                                    identifier, closed, config.strategy_version
                                )
                                counters.exits += 1

                if self._evaluation_boundary(timestamp, config) and symbol not in pending:
                    historical = HistoricalMarketContext(symbol, data[symbol], timestamp)
                    candidate = builder.build(historical)
                    opportunity = scoring.score_candidate(candidate)
                    analysis = strategy.evaluate(opportunity, candidate, timestamp)
                    setups = [
                        item
                        for item in analysis.results.values()
                        if item.strategy in config.strategies
                        and item.status == StrategyStatus.TRIGGERED
                        and item.opportunity_score >= config.minimum_opportunity_score
                        and item.setup_quality_score >= config.minimum_setup_score
                    ]
                    counters.setups_detected += len(setups)
                    for setup in sorted(setups, key=lambda item: item.strategy.value):
                        account = portfolio.account_snapshot(timestamp)
                        decision = risk.evaluate(
                            RiskContext(
                                evaluation_timestamp=timestamp,
                                account=account,
                                strategy_setup=setup,
                                instrument=candidate.instrument,
                                current_price=analysis.current_price,
                                atr=analysis.atr,
                                spread_percent=analysis.spread_percent,
                                estimated_slippage_percent=analysis.estimated_slippage_percent,
                                market_data_timestamp=timestamp,
                                liquidity_usable=True,
                            )
                        )
                        if decision.allowed:
                            counters.risk_approved_setups += 1
                            factors = {
                                item.factor_name.value: item.model_dump(mode="json")
                                for item in opportunity.factors
                            }
                            regime = (
                                candidate.volatility.regime or "unknown"
                            )
                            pending[symbol] = (
                                setup,
                                decision,
                                factors,
                                regime,
                                config.entry_delay_candles,
                            )
                            break
                        counters.risk_rejected_setups += 1
                portfolio.mark(timestamp)

            for symbol, position in list(portfolio.open_positions.items()):
                candle = last_candles[symbol]
                closed = execution.close(
                    position,
                    ExitFill(ExitReason.BACKTEST_END, candle.close),
                    candle.timestamp + TIMEFRAME_DURATION[candle.timeframe],
                )
                portfolio.record_close(identifier, closed, config.strategy_version)
                counters.exits += 1
            if events:
                portfolio.mark(events[-1][0])
            self._finish(result, portfolio, counters, config)
            result.warnings = list(
                dict.fromkeys(
                    [
                        *quality.warnings,
                        "Funding data unavailable; funding excluded.",
                        "Historical order-book depth unavailable; deterministic slippage model used.",
                        "Intrabar path is unknown; configured ambiguity policy applied.",
                        *(["Sample size may be insufficient for reliable conclusions."] if len(portfolio.trades) < 30 else []),
                    ]
                )
            )
            result.status = BacktestStatus.COMPLETED
            result.completed_at = datetime.now(UTC)
            structlog.get_logger().info(
                "BACKTEST_COMPLETED",
                backtest_id=str(identifier),
                trades=len(portfolio.trades),
                elapsed_seconds=perf_counter() - started,
            )
        except Exception as exc:  # noqa: BLE001 - result records isolated run failure
            result.status = BacktestStatus.FAILED
            result.error = f"{type(exc).__name__}: {exc}"
            result.completed_at = datetime.now(UTC)
            structlog.get_logger().error("BACKTEST_FAILED", backtest_id=str(identifier), error=result.error)
        return result

    async def _resolve_instruments(self, config: BacktestConfig) -> BacktestConfig:
        resolved = dict(config.instrument_overrides)
        getter = getattr(self.provider, "get_instrument", None)
        if getter:
            for symbol in config.symbols:
                if symbol not in resolved:
                    instrument = await getter(symbol)
                    if instrument is not None:
                        resolved[symbol] = instrument
        return config.model_copy(update={"instrument_overrides": resolved})

    async def _load(self, config):
        data = {}
        for symbol in config.symbols:
            frames = {}
            for timeframe in Timeframe:
                method = getattr(self.provider, "get_candles_with_warmup", None)
                if method:
                    frames[timeframe] = await method(
                        symbol,
                        timeframe,
                        config.start_timestamp,
                        config.end_timestamp,
                        config.warmup_candles,
                    )
                else:
                    frames[timeframe] = await self.provider.get_candles(
                        symbol, timeframe, config.start_timestamp, config.end_timestamp
                    )
            data[symbol] = frames
        return data

    @staticmethod
    def _events(data, config):
        events = []
        for symbol, frames in data.items():
            for candle in frames[Timeframe.MINUTE_5]:
                close = candle.timestamp + TIMEFRAME_DURATION[Timeframe.MINUTE_5]
                if config.start_timestamp <= close <= config.end_timestamp:
                    events.append((close, symbol, candle))
        return sorted(events, key=lambda item: (item[0], item[1]))

    @staticmethod
    def _evaluation_boundary(timestamp, config):
        duration = int(TIMEFRAME_DURATION[config.evaluation_timeframe].total_seconds())
        return int(timestamp.timestamp()) % duration == 0

    @staticmethod
    def _finish(result, portfolio, counters, config):
        trades = portfolio.trades
        curve = portfolio.equity_curve
        result.counters = counters
        result.trades = trades
        result.equity_curve = curve
        result.drawdown_curve = curve
        result.performance = performance(
            config.initial_equity,
            portfolio.equity,
            trades,
            curve,
            config.start_timestamp,
            config.end_timestamp,
        )
        result.execution_metrics = execution_metrics(trades, config.funding_included)
        result.risk_metrics = {
            "maximum_drawdown": result.performance.maximum_drawdown,
            "maximum_drawdown_percent": result.performance.maximum_drawdown_percent,
            "maximum_consecutive_losses": result.performance.maximum_consecutive_losses,
            "maximum_consecutive_wins": result.performance.maximum_consecutive_wins,
            "risk_per_trade_percent": config.risk.risk_per_trade_percent,
        }
        result.strategy_metrics = grouped(trades, lambda item: item.strategy.value)
        result.direction_metrics = grouped(trades, lambda item: item.direction.value)
        result.symbol_metrics = grouped(trades, lambda item: item.symbol)
        result.regime_metrics = grouped(trades, lambda item: item.market_regime)
        result.score_analysis = grouped(trades, lambda item: score_bucket(item.opportunity_score))
        result.setup_analysis = grouped(trades, lambda item: score_bucket(item.setup_score))
        result.r_distribution = r_distribution(trades)
        result.monthly_results = period_metrics(trades, monthly=True)
        result.daily_results = period_metrics(trades, monthly=False)
