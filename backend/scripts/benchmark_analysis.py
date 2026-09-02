"""Deterministic Phase 3 benchmark: 100 symbols x 6 timeframes x 220 candles."""

import json
import time
import tracemalloc
from datetime import UTC, datetime

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.domain.market import Timeframe
from app.market_data.models import CandleResult, NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION


def fixtures(symbol: str) -> dict[Timeframe, CandleResult]:
    frames = {}
    wave = (0, 0.4, 0.8, 0.4, 0, -0.4, -0.8, -0.4)
    for timeframe in Timeframe:
        duration = TIMEFRAME_DURATION[timeframe]
        start = datetime.now(UTC) - duration * 219
        candles = []
        for index in range(220):
            close = 100 + index * 0.05 + wave[index % len(wave)]
            candles.append(
                NormalizedCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=start + duration * index,
                    open=close - 0.1,
                    high=close + 0.5,
                    low=close - 0.5,
                    close=close,
                    volume=100 + index % 20,
                )
            )
        frames[timeframe] = CandleResult(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
    return frames


def run_batch(analyzer: MultiTimeframeAnalyzer, datasets) -> None:
    for symbol, frames in datasets:
        analyzer.analyze(symbol, frames)


def main() -> None:
    tracemalloc.start()
    datasets = [(f"B-TEST{index}_USDT", fixtures(f"B-TEST{index}_USDT")) for index in range(100)]
    fixture_memory, _ = tracemalloc.get_traced_memory()
    analyzer = MultiTimeframeAnalyzer()
    started = time.perf_counter()
    run_batch(analyzer, datasets)
    first_seconds = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    started = time.perf_counter()
    run_batch(analyzer, datasets)
    repeated_seconds = time.perf_counter() - started
    tracemalloc.stop()
    started = time.perf_counter()
    run_batch(analyzer, datasets)
    untraced_seconds = time.perf_counter() - started
    print(
        json.dumps(
            {
                "symbols": 100,
                "timeframes_per_symbol": 6,
                "candles_per_timeframe": 220,
                "analyses": 600,
                "first_run_seconds": round(first_seconds, 4),
                "repeated_run_seconds": round(repeated_seconds, 4),
                "repeated_to_first_ratio": round(repeated_seconds / first_seconds, 4),
                "untraced_run_seconds": round(untraced_seconds, 4),
                "fixture_memory_mib": round(fixture_memory / 1024 / 1024, 4),
                "traced_current_mib": round(current / 1024 / 1024, 4),
                "traced_peak_mib": round(peak / 1024 / 1024, 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
