import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import ScannerConfig
from .models import ScannerRunStatus, ScannerStatistics
from .scanner import AllMarketScanner
from .state import ScannerStateStore


class ScannerRuntime:
    JOB_ID = "all-market-futures-scan"

    def __init__(
        self,
        scanner: AllMarketScanner,
        state: ScannerStateStore,
        config: ScannerConfig,
        on_completed=None,
    ) -> None:
        self.scanner = scanner
        self.state = state
        self.config = config
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.on_completed = on_completed

    async def start_runtime(self) -> None:
        self.scheduler.start()
        if self.config.auto_start:
            await self.start_scanning()
        else:
            await self.state.mark_status(ScannerRunStatus.STOPPED)

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await self.state.mark_status(ScannerRunStatus.STOPPED)

    async def run_once(self) -> ScannerStatistics:
        stats = await self.scanner.scan_all_markets()
        if self.on_completed is not None:
            await self.on_completed(stats)
        return stats

    async def start_scanning(self) -> None:
        if self.scheduler.get_job(self.JOB_ID) is None:
            self.scheduler.add_job(
                self._scheduled_run,
                IntervalTrigger(seconds=self.config.interval_seconds),
                id=self.JOB_ID,
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
        self.state.scheduled = True
        await self.state.mark_status(ScannerRunStatus.IDLE)

    async def stop_scanning(self) -> None:
        if self.scheduler.get_job(self.JOB_ID):
            self.scheduler.remove_job(self.JOB_ID)
        self.state.scheduled = False
        await self.state.mark_status(ScannerRunStatus.STOPPED)

    async def _scheduled_run(self) -> None:
        try:
            await self.run_once()
        except Exception as exc:  # noqa: BLE001 - scheduler must remain alive
            structlog.get_logger().error("SCANNER_SCHEDULED_RUN_ERROR", error=str(exc))
            await asyncio.sleep(0)
