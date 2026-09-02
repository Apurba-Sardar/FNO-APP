"""Deterministic Phase 5 benchmark for 100 six-timeframe candidates."""

import json
import time
import tracemalloc
from datetime import UTC, datetime

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.domain.market import Timeframe
from app.market_data.models import CandleResult, NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION
from app.scanner.models import (
    CandidateStatus,
    LiquidityClassification,
    LiquiditySnapshot,
    MarketScanMetrics,
    MetricStatus,
    ScannerCandidate,
    ScannerDirection,
    TechnicalActivity,
    VolatilitySnapshot,
    VolatilitySuitability,
    VolumeActivity,
    VolumeSnapshot,
)
from app.scoring.engine import OpportunityScoringEngine
from app.scoring.ranking import OpportunityRankingService


def candidate(symbol: str) -> ScannerCandidate:
    now = datetime.now(UTC)
    frames = {}
    wave = (0, 1, 2, 1, 0, -1, -2, -1)
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        start = now - duration * 219
        candles = []
        for index in range(220):
            close = 100 + 0.2 * index + wave[index % len(wave)]
            candles.append(
                NormalizedCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=start + duration * index,
                    open=close - 0.1,
                    high=close + 1.5,
                    low=close - 1.5,
                    close=close,
                    volume=100 + index % 20,
                )
            )
        frames[timeframe] = CandleResult(symbol=symbol, timeframe=timeframe, candles=candles)
    analysis = MultiTimeframeAnalyzer().analyze(symbol, frames)
    frame = analysis.timeframes[Timeframe.MINUTE_15]
    return ScannerCandidate(
        symbol=symbol,
        scan_timestamp=now,
        processing_duration_ms=1,
        status=CandidateStatus.ELIGIBLE,
        market=MarketScanMetrics(
            last_price=frame.indicators.close,
            price_change_percent_24h=5,
            volume_24h=10_000_000,
            data_timestamp=now,
            fresh=True,
        ),
        liquidity=LiquiditySnapshot(
            classification=LiquidityClassification.EXCELLENT,
            spread_status=MetricStatus.KNOWN,
            spread_percent=0.01,
            slippage_status=MetricStatus.KNOWN,
            estimated_slippage_percent=0.02,
            bid_depth_quote=500_000,
            ask_depth_quote=500_000,
            orderbook_timestamp=now,
        ),
        volume=VolumeSnapshot(
            current_volume=500,
            volume_ma=200,
            relative_volume=2.5,
            trend="increasing",
            activity=VolumeActivity.HIGH_ACTIVITY,
            spike=True,
        ),
        volatility=VolatilitySnapshot(
            atr=frame.indicators.atr,
            atr_percent=frame.indicators.atr_percent,
            recent_range_expansion=1.2,
            regime="normal",
            suitability=VolatilitySuitability.SUITABLE,
        ),
        timeframes=analysis.timeframes,
        dominant_direction=ScannerDirection.BULLISH,
        timeframe_alignment=analysis.alignment.alignment_state.value,
        alignment_ratio=analysis.alignment.alignment_ratio,
        technical_activity=TechnicalActivity.HIGH_ACTIVITY,
        data_quality_status="healthy",
    )


def main() -> None:
    fixture = candidate("B-TEST0_USDT")
    candidates = []
    for index in range(100):
        symbol = f"B-TEST{index}_USDT"
        candidates.append(
            fixture.model_copy(
                update={
                    "symbol": symbol,
                    "timeframes": {
                        timeframe: analysis.model_copy(update={"symbol": symbol})
                        for timeframe, analysis in fixture.timeframes.items()
                    },
                }
            )
        )
    engine = OpportunityScoringEngine()
    ranking = OpportunityRankingService()
    tracemalloc.start()
    started = time.perf_counter()
    opportunities = [engine.score_candidate(item) for item in candidates]
    scoring_seconds = time.perf_counter() - started
    ranking_started = time.perf_counter()
    ranked, ranking_ms = ranking.rank(opportunities)
    ranking_seconds = time.perf_counter() - ranking_started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        json.dumps(
            {
                "markets": len(candidates),
                "timeframes_per_market": 6,
                "factors_per_direction": 10,
                "total_scoring_seconds": round(scoring_seconds, 6),
                "average_scoring_ms": round(scoring_seconds / len(candidates) * 1000, 6),
                "ranking_seconds": round(ranking_seconds, 6),
                "reported_ranking_ms": round(ranking_ms, 6),
                "eligible": sum(item.eligible for item in ranked),
                "current_memory_mib": round(current / 1024 / 1024, 6),
                "peak_memory_mib": round(peak / 1024 / 1024, 6),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
