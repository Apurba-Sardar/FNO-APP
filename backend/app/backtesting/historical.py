
from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.domain.market import Timeframe
from app.indicators.engine import IndicatorEngine
from app.indicators.models import MultiTimeframeAnalysis, MultiTimeframeDataQuality
from app.scanner.filters import (
    classify_direction,
    classify_technical_activity,
    classify_volatility,
    classify_volume,
)
from app.scanner.models import (
    CandidateStatus,
    LiquidityClassification,
    LiquiditySnapshot,
    MarketScanMetrics,
    MetricStatus,
    ScannerCandidate,
)

from .config import BacktestConfig
from .context import HistoricalMarketContext


class HistoricalCandidateBuilder:
    """Adapts point-in-time candles to existing Phase 5/6 normalized inputs."""

    def __init__(self, config: BacktestConfig, indicators: IndicatorEngine | None = None) -> None:
        self.config = config
        self.indicators = indicators or IndicatorEngine()

    def build(self, context: HistoricalMarketContext) -> ScannerCandidate:
        analyses = {}
        warnings = [
            "historical order-book data unavailable; configured execution assumptions used",
            "historical market-universe metadata is limited to stored instruments",
        ]
        recent = {}
        for timeframe in Timeframe:
            rows = context.closed_candles(timeframe, self.config.warmup_candles)
            context.assert_not_future(rows)
            recent[timeframe] = rows
            analyses[timeframe] = self.indicators.analyze(
                context.symbol,
                timeframe,
                rows,
                evaluation_timestamp=context.evaluation_timestamp,
            )
        alignment = MultiTimeframeAnalyzer.alignment(analyses)
        complete = all(item.data_quality.sufficient_data for item in analyses.values())
        multi = MultiTimeframeAnalysis(
            symbol=context.symbol,
            generated_at=context.evaluation_timestamp,
            timeframes=analyses,
            alignment=alignment,
            data_quality=MultiTimeframeDataQuality(
                sufficient_data=complete,
                analysis_completeness=sum(
                    item.data_quality.analysis_completeness for item in analyses.values()
                )
                / len(Timeframe),
                warnings=warnings,
            ),
        )
        lower = analyses[Timeframe.MINUTE_5]
        indicator = lower.indicators
        volatility = classify_volatility(
            indicator.atr if indicator else None,
            indicator.atr_percent if indicator else None,
            lower.volatility.recent_range_expansion if lower.volatility else None,
            lower.volatility.regime.value if lower.volatility and lower.volatility.regime else None,
            _scanner_config(self.config),
        )
        volume = classify_volume(
            indicator.volume if indicator else None,
            indicator.volume_ma if indicator else None,
            indicator.relative_volume if indicator else None,
            "increasing" if indicator and indicator.volume_increasing else "decreasing",
            _scanner_config(self.config),
        )
        price = indicator.close if indicator else None
        spread = self.config.historical_spread_percent
        slippage = self.config.slippage_model.entry_slippage_bps / 100
        liquidity = LiquiditySnapshot(
            classification=LiquidityClassification.ACCEPTABLE,
            spread_status=MetricStatus.KNOWN,
            spread_percent=spread,
            slippage_status=MetricStatus.KNOWN,
            estimated_slippage_percent=slippage,
            orderbook_timestamp=context.evaluation_timestamp,
        )
        return ScannerCandidate(
            symbol=context.symbol,
            scan_timestamp=context.evaluation_timestamp,
            processing_duration_ms=0,
            status=CandidateStatus.ELIGIBLE if complete and price else CandidateStatus.INSUFFICIENT_DATA,
            market=MarketScanMetrics(
                last_price=price,
                volume_24h=sum(row.close * row.volume for row in recent[Timeframe.MINUTE_5][-288:]),
                data_timestamp=context.evaluation_timestamp,
                fresh=True,
            ),
            liquidity=liquidity,
            volume=volume,
            volatility=volatility,
            timeframes=analyses,
            recent_candles=recent,
            dominant_direction=classify_direction(multi),
            timeframe_alignment=alignment.alignment_state.value,
            alignment_ratio=alignment.alignment_ratio,
            technical_activity=classify_technical_activity(multi, volume, volatility),
            data_quality_status="healthy" if complete else "insufficient_data",
            warnings=warnings,
            instrument=self.config.instrument_overrides.get(context.symbol),
        )


def _scanner_config(config: BacktestConfig):
    from app.scanner.config import ScannerConfig

    return ScannerConfig(
        max_spread_percent=config.risk.max_spread_percent,
        max_slippage_percent=config.risk.max_estimated_slippage_percent,
    )
