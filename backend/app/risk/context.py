from app.scanner.models import LiquidityClassification, ScannerCandidate
from app.strategy.models import StrategyResult, SymbolStrategyAnalysis

from .models import AccountSnapshot, RiskContext


class RiskContextBuilder:
    """Maps normalized Phase 2/4/6 models into an execution-agnostic risk context."""

    @staticmethod
    def build(
        analysis: SymbolStrategyAnalysis,
        setup: StrategyResult,
        candidate: ScannerCandidate,
        account: AccountSnapshot,
        evaluation_timestamp,
        instrument_override=None,
    ) -> RiskContext:
        timestamps = [
            value
            for value in (
                candidate.market.data_timestamp,
                candidate.liquidity.orderbook_timestamp,
            )
            if value is not None
        ]
        # The oldest mandatory market snapshot controls freshness.
        market_timestamp = min(timestamps) if len(timestamps) == 2 else None
        return RiskContext(
            evaluation_timestamp=evaluation_timestamp,
            account=account,
            strategy_setup=setup,
            instrument=instrument_override or candidate.instrument,
            current_price=analysis.current_price,
            atr=analysis.atr,
            spread_percent=analysis.spread_percent,
            estimated_slippage_percent=analysis.estimated_slippage_percent,
            market_data_timestamp=market_timestamp,
            liquidity_usable=candidate.liquidity.classification
            in {
                LiquidityClassification.EXCELLENT,
                LiquidityClassification.GOOD,
                LiquidityClassification.ACCEPTABLE,
            },
            correlation_group="broad_crypto_market",
        )
