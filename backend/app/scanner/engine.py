import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol

from app.analysis.multi_timeframe import LegacyMultiTimeframeAnalyzer
from app.clients.coindcx import CoinDCXPublicClient
from app.config import ScannerSettings
from app.domain.analysis import Opportunity
from app.domain.market import Instrument, Timeframe
from app.market_data.orderbook import InsufficientDepthError, analyze_order_book
from app.services.candles import CandleService


class LegacyScorer(Protocol):
    """Injected Phase 1 compatibility boundary for the retired scanner adapter."""

    weights: Any

    def score(self, inputs: Any) -> tuple[float, dict[str, float]]: ...


class MarketRejected(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


class MarketScanner:
    def __init__(
        self,
        client: CoinDCXPublicClient,
        candles: CandleService,
        analyzer: LegacyMultiTimeframeAnalyzer,
        scorer: LegacyScorer,
        config: ScannerSettings,
        concurrency: int = 5,
    ) -> None:
        self.client = client
        self.candles = candles
        self.analyzer = analyzer
        self.scorer = scorer
        self.config = config
        self._semaphore = asyncio.Semaphore(concurrency)

    async def scan_pair(self, instrument: Instrument, risk_reward: float = 2) -> Opportunity:
        hard_failures = []
        if instrument.status != "active":
            hard_failures.append("instrument is not active")
        book = await self.client.get_order_book(instrument.pair, self.config.depth_levels)
        age = (datetime.now(UTC) - book.timestamp).total_seconds()
        if age > self.config.max_data_age_seconds:
            hard_failures.append("order book is stale")
        try:
            metrics = analyze_order_book(
                book,
                self.config.depth_window_bps,
                self.config.slippage_test_notional,
            )
        except (InsufficientDepthError, ValueError) as exc:
            raise MarketRejected([str(exc)]) from exc
        if metrics.spread_bps > self.config.max_spread_bps:
            hard_failures.append("spread exceeds hard limit")
        if metrics.estimated_slippage_bps > self.config.max_slippage_bps:
            hard_failures.append("estimated slippage exceeds hard limit")
        frames = {}
        for timeframe in Timeframe:
            frames[timeframe] = await self.candles.history(
                instrument.pair, timeframe, self.config.min_history_bars
            )
            if len(frames[timeframe]) < self.config.min_history_bars:
                hard_failures.append(f"insufficient {timeframe.value} history")
        latest = frames[Timeframe.MINUTE_5][-1] if frames[Timeframe.MINUTE_5] else None
        quote_volume = sum(x.volume * x.close for x in frames[Timeframe.MINUTE_5][-288:])
        if quote_volume < self.config.min_quote_volume:
            hard_failures.append("insufficient rolling quote volume")
        if (
            latest
            and (datetime.now(UTC) - latest.time).total_seconds()
            > self.config.max_data_age_seconds + 300
        ):
            hard_failures.append("candles are stale")
        if hard_failures:
            raise MarketRejected(sorted(set(hard_failures)))
        liquidity = (
            1
            - min(metrics.spread_bps / self.config.max_spread_bps, 1) * 0.5
            - min(metrics.estimated_slippage_bps / self.config.max_slippage_bps, 1) * 0.5
        )
        direction, inputs, snapshots = self.analyzer.analyze(frames, liquidity, risk_reward)
        score, components = self.scorer.score(inputs)
        reasons = [
            name.replace("_", " ")
            for name, value in components.items()
            if value >= getattr(self.scorer.weights, name) * 0.75
        ]
        warnings = ["neutral higher-timeframe direction"] if direction.value == "neutral" else []
        return Opportunity(
            pair=instrument.pair,
            score=score,
            direction=direction,
            status="eligible",
            metrics={
                **components,
                "spread_bps": round(metrics.spread_bps, 4),
                "slippage_bps": round(metrics.estimated_slippage_bps, 4),
                "relative_volume": round(snapshots[Timeframe.MINUTE_5].relative_volume or 0, 4),
                "risk_reward": risk_reward,
            },
            reasons=reasons,
            warnings=warnings,
        )

    async def scan(
        self, instruments: list[Instrument]
    ) -> tuple[list[Opportunity], dict[str, list[str]]]:
        async def one(item: Instrument):
            async with self._semaphore:
                try:
                    return await self.scan_pair(item)
                except MarketRejected as exc:
                    return (item.pair, exc.reasons)

        results = await asyncio.gather(*(one(item) for item in instruments))
        opportunities = [x for x in results if isinstance(x, Opportunity)]
        rejected = {x[0]: x[1] for x in results if isinstance(x, tuple)}
        return sorted(opportunities, key=lambda x: x.score, reverse=True), rejected
