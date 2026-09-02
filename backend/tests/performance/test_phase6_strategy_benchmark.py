import time
import tracemalloc

from tests.phase6_fixtures import strategy_fixture


def test_strategy_benchmark_100_symbols_six_timeframes_two_strategies(monkeypatch):
    class QuietLogger:
        def info(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("app.strategy.engine.structlog.get_logger", lambda: QuietLogger())
    market, opportunity, _, _, engine = strategy_fixture()
    samples = []
    for index in range(100):
        symbol = f"B-BENCH{index:03d}_USDT"
        samples.append(
            (
                market.model_copy(update={"symbol": symbol}),
                opportunity.model_copy(update={"symbol": symbol}),
            )
        )
    tracemalloc.start()
    started = time.perf_counter()
    results = [engine.evaluate(item, candidate, candidate.scan_timestamp) for candidate, item in samples]
    duration = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    repeated_started = time.perf_counter()
    repeated = [
        engine.evaluate(item, candidate, candidate.scan_timestamp) for candidate, item in samples
    ]
    repeated_duration = time.perf_counter() - repeated_started
    context_started = time.perf_counter()
    contexts = [
        engine.context_builder.build(item, candidate, candidate.scan_timestamp)
        for candidate, item in samples
    ]
    context_duration = time.perf_counter() - context_started
    strategy_timings = {}
    for strategy in engine.strategies:
        strategy_started = time.perf_counter()
        [strategy.evaluate(context) for context in contexts]
        strategy_timings[strategy.name.value] = time.perf_counter() - strategy_started
    print(
        "phase6 benchmark: 100 symbols x 6 frames x 2 strategies: "
        f"{duration:.3f}s instrumented, {repeated_duration:.3f}s repeated, "
        f"{repeated_duration / 100 * 1000:.2f}ms/market, "
        f"context {context_duration:.3f}s, strategies {strategy_timings}, "
        f"peak {peak / 1024 / 1024:.2f} MiB"
    )
    assert len(results) == 100
    assert sum(len(item.results) for item in results) == 200
    assert len(repeated) == 100
    assert duration < 30
    assert peak < 500 * 1024 * 1024
