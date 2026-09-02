from time import perf_counter

from app.backtesting.validation import validate_historical_data
from app.domain.market import Timeframe
from app.market_data.models import NormalizedCandle
from app.market_data.normalization import TIMEFRAME_DURATION
from tests.phase8_fixtures import NOW


def test_phase8_data_pipeline_benchmark_100_symbols_six_timeframes():
    started = perf_counter()
    data = {}
    for symbol_index in range(100):
        symbol = f"B-SYNTH{symbol_index}_USDT"
        data[symbol] = {}
        for timeframe in Timeframe:
            duration = TIMEFRAME_DURATION[timeframe]
            data[symbol][timeframe] = [
                NormalizedCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=NOW + index * duration,
                    open=100,
                    high=101,
                    low=99,
                    close=100,
                    volume=100,
                )
                for index in range(220)
            ]
    construction_seconds = perf_counter() - started
    validation_started = perf_counter()
    report = validate_historical_data(data, 220)
    validation_seconds = perf_counter() - validation_started
    total_seconds = perf_counter() - started
    print(
        "phase8 benchmark: 100 symbols x 6 timeframes x 220 candles "
        f"({report.candles_checked} candles); construction={construction_seconds:.4f}s; "
        f"validation={validation_seconds:.4f}s; total={total_seconds:.4f}s"
    )
    assert report.valid
    assert report.candles_checked == 132_000
    assert total_seconds < 15
