import structlog

from app.domain.market import Timeframe

from .breakout import BreakoutStrategy
from .config import StrategyConfig
from .models import StrategyStatus, SymbolStrategyAnalysis
from .trend_pullback import TrendPullbackStrategy


class StrategyEngine:
    """Pure deterministic evaluator. It has no exchange, database, or executor dependency."""

    def __init__(self, context_builder, config: StrategyConfig) -> None:
        self.context_builder = context_builder
        self.config = config
        self.strategies = (
            TrendPullbackStrategy(config),
            BreakoutStrategy(config),
        )

    def evaluate(self, opportunity, candidate, evaluation_timestamp) -> SymbolStrategyAnalysis:
        context = self.context_builder.build(opportunity, candidate, evaluation_timestamp)
        results = {strategy.name: strategy.evaluate(context) for strategy in self.strategies}
        viable = [result for result in results.values() if result.status != StrategyStatus.NO_SETUP]
        best = max(viable, key=lambda item: (item.setup_quality_score, item.risk_reward or 0), default=None)
        setup = context.timeframes.get(Timeframe.MINUTE_15)
        support = [level.price for level in setup.structure.support_levels] if setup else []
        resistance = [level.price for level in setup.structure.resistance_levels] if setup else []
        for result in results.values():
            structlog.get_logger().info(
                "STRATEGY_EVALUATION",
                symbol=result.symbol,
                strategy=result.strategy.value,
                status=result.status.value,
                direction=result.direction.value,
                quality=result.setup_quality_score,
                evaluation_timestamp=result.evaluation_timestamp.isoformat(),
            )
            structlog.get_logger().info(
                f"STRATEGY_{result.status.value.upper()}",
                symbol=result.symbol,
                strategy=result.strategy.value,
                status=result.status.value,
                score=result.setup_quality_score,
                evaluation_timestamp=result.evaluation_timestamp.isoformat(),
            )
        return SymbolStrategyAnalysis(
            symbol=context.symbol,
            evaluation_timestamp=evaluation_timestamp,
            opportunity_score=opportunity.opportunity_score,
            current_price=context.current_price,
            timeframe_trends={timeframe: frame.trend.value for timeframe, frame in context.timeframes.items()},
            relative_volume=context.market.volume.relative_volume,
            atr=context.market.volatility.atr,
            spread_percent=context.market.liquidity.spread_percent,
            estimated_slippage_percent=context.market.liquidity.estimated_slippage_percent,
            results=results,
            best_setup=best,
            chart=context.chart,
            support_levels=support,
            resistance_levels=resistance,
            warnings=context.warnings,
        )
