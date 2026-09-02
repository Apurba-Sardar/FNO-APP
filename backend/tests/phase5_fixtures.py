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


def candidate(slope: float = 0.2, symbol: str = "B-TEST_USDT") -> ScannerCandidate:
    frames = {}
    wave = (0, 1, 2, 1, 0, -1, -2, -1)
    now = datetime.now(UTC)
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        start = now - duration * 219
        candles = []
        for index in range(220):
            close = 100 + slope * index + wave[index % len(wave)]
            candles.append(
                NormalizedCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=start + duration * index,
                    open=close - slope / 2,
                    high=close + 1.5,
                    low=close - 1.5,
                    close=close,
                    volume=100 + index % 20,
                )
            )
        frames[timeframe] = CandleResult(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
    analysis = MultiTimeframeAnalyzer().analyze(symbol, frames)
    fifteen = analysis.timeframes[Timeframe.MINUTE_15]
    price = fifteen.indicators.close
    atr = fifteen.indicators.atr
    direction = ScannerDirection.BULLISH if slope > 0 else ScannerDirection.BEARISH
    return ScannerCandidate(
        symbol=symbol,
        scan_timestamp=now,
        processing_duration_ms=1,
        status=CandidateStatus.ELIGIBLE,
        market=MarketScanMetrics(
            last_price=price,
            price_change_percent_24h=5 if slope > 0 else -5,
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
            atr=atr,
            atr_percent=atr / price * 100,
            recent_range_expansion=1.2,
            regime="normal",
            suitability=VolatilitySuitability.SUITABLE,
        ),
        timeframes=analysis.timeframes,
        recent_candles={timeframe: result.candles for timeframe, result in frames.items()},
        dominant_direction=direction,
        timeframe_alignment=analysis.alignment.alignment_state.value,
        alignment_ratio=analysis.alignment.alignment_ratio,
        technical_activity=TechnicalActivity.HIGH_ACTIVITY,
        data_quality_status="healthy",
    )
