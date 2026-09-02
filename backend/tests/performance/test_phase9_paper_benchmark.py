from time import perf_counter

from tests.phase9_fixtures import NOW, approved, harness, quote, triggered


def test_paper_execution_benchmark_100_markets():
    _, _, state, executor = harness()
    started = perf_counter()
    for index in range(100):
        symbol = f"B-SIM{index}_USDT"
        executor.execute_entry(
            state,
            triggered(symbol=symbol),
            approved(symbol=symbol),
            quote(symbol=symbol),
            NOW,
            f"{symbol}:trend_pullback:{NOW.isoformat()}",
        )
    elapsed = perf_counter() - started
    print(f"phase9 benchmark: 100 markets, 100 fills, total={elapsed:.6f}s, per_fill_ms={elapsed * 10:.4f}")
    assert len(state.positions) == 100
    assert elapsed < 5
