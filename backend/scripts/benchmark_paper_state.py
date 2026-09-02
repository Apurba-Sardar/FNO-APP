"""Measure durable Phase 9 snapshot writes against the configured PostgreSQL database."""

import asyncio
from statistics import mean
from time import perf_counter

from app.db.session import SessionLocal
from app.paper_trading.state import PaperStateRepository


async def main(samples: int = 10) -> None:
    repository = PaperStateRepository(SessionLocal, 100_000)
    state = await repository.load()
    durations = []
    for _ in range(samples):
        started = perf_counter()
        await repository.save(state)
        durations.append((perf_counter() - started) * 1000)
    print(
        f"phase9 postgres snapshot writes: count={samples}; "
        f"average_ms={mean(durations):.3f}; maximum_ms={max(durations):.3f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
