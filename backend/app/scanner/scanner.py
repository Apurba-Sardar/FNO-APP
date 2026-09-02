import asyncio
from collections import Counter
from datetime import UTC, datetime
from time import perf_counter

import structlog

from app.analysis.multi_timeframe import MultiTimeframeAnalyzer
from app.config import Settings
from app.domain.market import Timeframe
from app.indicators import IndicatorEngine
from app.market_data.candles import HistoricalCandleService
from app.market_data.discovery import MarketDiscoveryService
from app.market_data.models import Market
from app.market_data.normalization import (
    epoch_milliseconds,
    normalize_market,
    normalize_websocket_orderbook,
)
from app.market_data.service import MarketDataService
from app.services.coindcx.public_client import CoinDCXPublicClient

from .config import ScannerConfig
from .exceptions import ScanAlreadyRunning
from .filters import (
    analyze_liquidity,
    classify_direction,
    classify_technical_activity,
    classify_volatility,
    classify_volume,
)
from .models import (
    CandidateStatus,
    LiquidityClassification,
    LiquiditySnapshot,
    MarketScanMetrics,
    MetricStatus,
    ScannerCandidate,
    ScannerDirection,
    ScannerRunStatus,
    ScannerStatistics,
    TechnicalActivity,
    VolatilitySnapshot,
    VolatilitySuitability,
    VolumeActivity,
    VolumeSnapshot,
)
from .state import ScannerStateStore


class AllMarketScanner:
    """Read-only all-market candidate scanner. It never produces trade decisions."""

    def __init__(
        self,
        settings: Settings,
        config: ScannerConfig,
        state: ScannerStateStore,
        cache,
        client_factory=None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.state = state
        self.cache = cache
        self.analyzer = MultiTimeframeAnalyzer(IndicatorEngine(settings.analysis))
        self.client_factory = client_factory or self._default_client
        self._cycle_lock = asyncio.Lock()
        self._analysis_seconds = 0.0

    async def scan_all_markets(self) -> ScannerStatistics:
        if self._cycle_lock.locked():
            raise ScanAlreadyRunning("a full scanner cycle is already running")
        async with self._cycle_lock:
            await self.state.mark_status(ScannerRunStatus.RUNNING)
            started_at = datetime.now(UTC)
            started = perf_counter()
            self._analysis_seconds = 0.0
            try:
                candidates, api_requests, discovery_errors = await self._run_cycle(started_at)
                completed = datetime.now(UTC)
                elapsed = perf_counter() - started
                stats = self._statistics(
                    candidates,
                    started_at,
                    completed,
                    elapsed,
                    api_requests,
                    discovery_errors,
                )
                symbol_states = {
                    candidate.symbol: self.state.new_symbol_state(
                        candidate, self.state.symbols.get(candidate.symbol)
                    )
                    for candidate in candidates
                }
                await self.state.replace(candidates, symbol_states, stats)
                await self.state.mark_status(
                    ScannerRunStatus.IDLE if self.state.scheduled else ScannerRunStatus.STOPPED
                )
                structlog.get_logger().info(
                    "SCANNER_CYCLE_COMPLETED",
                    total=stats.total_markets,
                    eligible=stats.eligible_markets,
                    seconds=stats.processing_time_seconds,
                )
                return stats
            except Exception as exc:
                await self.state.mark_status(ScannerRunStatus.ERROR, error=str(exc))
                structlog.get_logger().error("SCANNER_CYCLE_ERROR", error=str(exc))
                raise

    async def _run_cycle(self, scan_timestamp: datetime) -> tuple[list[ScannerCandidate], int, int]:
        async with self.client_factory() as client:
            markets, discovery_errors = await MarketDiscoveryService(client).get_eligible_markets()
            price_snapshot = await client.current_prices()
            tickers = price_snapshot.prices
            ticker_timestamp = epoch_milliseconds(price_snapshot.ts)
            candle_service = HistoricalCandleService(
                client,
                cache=self.cache,
                cache_ttl_seconds=self.settings.candle_cache_ttl_seconds,
            )
            market_data = MarketDataService(client, candle_service, cache=self.cache)
            semaphore = asyncio.Semaphore(self.config.max_concurrency)

            async def process(market: Market) -> ScannerCandidate:
                async with semaphore:
                    try:
                        return await self._scan_market(
                            market,
                            tickers.get(market.symbol),
                            ticker_timestamp,
                            client,
                            market_data,
                            scan_timestamp,
                        )
                    except Exception as exc:  # noqa: BLE001 - symbol isolation is mandatory
                        structlog.get_logger().warning(
                            "SCANNER_SYMBOL_ERROR",
                            symbol=market.symbol,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        return self._diagnostic_candidate(
                            market.symbol,
                            scan_timestamp,
                            CandidateStatus.DATA_ERROR,
                            f"unexpected_error: {type(exc).__name__}: {exc}",
                        )

            candidates = await asyncio.gather(*(process(market) for market in markets))
            return list(candidates), client.request_count, len(discovery_errors)

    def _default_client(self) -> CoinDCXPublicClient:
        return CoinDCXPublicClient(
            self.settings.coindcx_api_base_url,
            self.settings.coindcx_public_base_url,
            self.settings.request_timeout_seconds,
            requests_per_second=self.settings.coindcx_requests_per_second,
            max_retries=self.settings.coindcx_max_retries,
        )

    async def _scan_market(
        self,
        market: Market,
        raw_ticker: dict | None,
        ticker_timestamp: datetime,
        client: CoinDCXPublicClient,
        market_data: MarketDataService,
        scan_timestamp: datetime,
    ) -> ScannerCandidate:
        started = perf_counter()
        if market.status != "active":
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.FILTERED,
                "filtered_by_eligibility: inactive market",
                started,
            )
        ticker = self._market_metrics(raw_ticker, ticker_timestamp, scan_timestamp)
        if ticker.last_price is None:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.DATA_ERROR,
                "invalid market price",
                started,
                ticker,
            )
        if not ticker.fresh:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.STALE,
                "stale ticker data",
                started,
                ticker,
            )
        if ticker.volume_24h is None or ticker.volume_24h < self.config.min_volume_24h:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.FILTERED,
                "filtered_by_volume: 24h volume below configured minimum",
                started,
                ticker,
            )

        book = None
        orderbook_warning = None
        try:
            raw_book = await client.orderbook(market.symbol, self.config.orderbook_depth)
            book = normalize_websocket_orderbook(market.symbol, raw_book.model_dump())
        except Exception as exc:  # noqa: BLE001 - unknown policy determines eligibility
            orderbook_warning = f"order book unavailable: {type(exc).__name__}"
        liquidity = analyze_liquidity(book, self.config, now=scan_timestamp)
        unknown_liquidity = (
            liquidity.spread_status == MetricStatus.UNKNOWN
            or liquidity.slippage_status == MetricStatus.UNKNOWN
        )
        if unknown_liquidity and not self.config.unknown_liquidity_eligible:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.FILTERED,
                "filtered_by_liquidity: spread or slippage is unknown",
                started,
                ticker,
                liquidity,
            )
        if liquidity.classification in {
            LiquidityClassification.POOR,
            LiquidityClassification.UNUSABLE,
        } and not (unknown_liquidity and self.config.unknown_liquidity_eligible):
            reason = (
                "filtered_by_spread: spread exceeds configured maximum"
                if liquidity.spread_percent is not None
                and liquidity.spread_percent > self.config.max_spread_percent
                else "filtered_by_liquidity: insufficient depth or excessive slippage"
            )
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.FILTERED,
                reason,
                started,
                ticker,
                liquidity,
            )

        fetched = await market_data.get_multi_timeframe_candles(
            market.symbol, list(Timeframe), self.config.history_limit
        )
        if fetched.errors or len(fetched.results) != len(Timeframe):
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.INSUFFICIENT_DATA,
                "filtered_by_data_quality: missing timeframe candles",
                started,
                ticker,
                liquidity,
            )
        analysis_started = perf_counter()
        analysis = self.analyzer.analyze(market.symbol, fetched.results)
        self._analysis_seconds += perf_counter() - analysis_started
        if analysis.data_quality.stale_timeframes:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.STALE,
                "filtered_by_data_quality: stale candle data",
                started,
                ticker,
                liquidity,
            )
        if not analysis.data_quality.sufficient_data:
            return self._diagnostic_candidate(
                market.symbol,
                scan_timestamp,
                CandidateStatus.INSUFFICIENT_DATA,
                "filtered_by_data_quality: insufficient or invalid candles",
                started,
                ticker,
                liquidity,
            )

        activity_frame = analysis.timeframes[Timeframe.MINUTE_15]
        indicators = activity_frame.indicators
        volatility_analysis = activity_frame.volatility
        volume = classify_volume(
            indicators.volume if indicators else None,
            indicators.volume_ma if indicators else None,
            indicators.relative_volume if indicators else None,
            (
                "increasing"
                if indicators and indicators.volume_increasing
                else "decreasing"
                if indicators and indicators.volume_decreasing
                else "flat_or_unavailable"
            ),
            self.config,
        )
        volatility = classify_volatility(
            volatility_analysis.atr if volatility_analysis else None,
            volatility_analysis.atr_percent if volatility_analysis else None,
            volatility_analysis.recent_range_expansion if volatility_analysis else None,
            volatility_analysis.regime.value
            if volatility_analysis and volatility_analysis.regime
            else None,
            self.config,
        )
        direction = classify_direction(analysis)
        technical = classify_technical_activity(analysis, volume, volatility)
        warnings = [orderbook_warning] if orderbook_warning else []
        detailed_market = market
        try:
            detailed_market = normalize_market(await client.instrument(market.symbol))
        except Exception as exc:  # noqa: BLE001 - constraints remain explicitly unavailable
            warnings.append(f"instrument constraints unavailable: {type(exc).__name__}")
        status = CandidateStatus.WARNING if unknown_liquidity else CandidateStatus.ELIGIBLE
        if volatility.suitability == VolatilitySuitability.TOO_LOW:
            status = CandidateStatus.FILTERED
            warnings.append("filtered_by_volatility: ATR percent is too low")
        elif (
            volatility.suitability == VolatilitySuitability.EXTREME
            and self.config.filter_extreme_volatility
        ):
            status = CandidateStatus.FILTERED
            warnings.append("filtered_by_volatility: ATR percent is extreme")
        if technical == TechnicalActivity.DORMANT and self.config.filter_dormant_activity:
            status = CandidateStatus.FILTERED
            warnings.append("filtered_by_technical_activity: market is dormant")
        return ScannerCandidate(
            symbol=market.symbol,
            scan_timestamp=scan_timestamp,
            processing_duration_ms=(perf_counter() - started) * 1000,
            status=status,
            market=ticker,
            liquidity=liquidity,
            volume=volume,
            volatility=volatility,
            timeframes=analysis.timeframes,
            recent_candles={
                timeframe: result.candles[-self.config.candidate_candle_limit :]
                for timeframe, result in fetched.results.items()
            },
            dominant_direction=direction,
            timeframe_alignment=analysis.alignment.alignment_state.value,
            alignment_ratio=analysis.alignment.alignment_ratio,
            technical_activity=technical,
            data_quality_status="healthy",
            warnings=warnings,
            instrument=detailed_market,
        )

    def _market_metrics(
        self, raw: dict | None, timestamp: datetime, now: datetime
    ) -> MarketScanMetrics:
        raw = raw or {}
        price = raw.get("ls") or raw.get("mp")
        price = float(price) if price is not None and float(price) > 0 else None
        age = (now - timestamp).total_seconds()
        return MarketScanMetrics(
            last_price=price,
            price_change_percent_24h=raw.get("pc"),
            volume_24h=raw.get("v"),
            data_timestamp=timestamp,
            fresh=age <= self.config.max_ticker_age_seconds,
        )

    def _diagnostic_candidate(
        self,
        symbol: str,
        scan_timestamp: datetime,
        status: CandidateStatus,
        warning: str,
        started: float | None = None,
        market: MarketScanMetrics | None = None,
        liquidity: LiquiditySnapshot | None = None,
    ) -> ScannerCandidate:
        return ScannerCandidate(
            symbol=symbol,
            scan_timestamp=scan_timestamp,
            processing_duration_ms=0 if started is None else (perf_counter() - started) * 1000,
            status=status,
            market=market or MarketScanMetrics(),
            liquidity=liquidity
            or LiquiditySnapshot(
                classification=LiquidityClassification.UNUSABLE,
                spread_status=MetricStatus.UNKNOWN,
                slippage_status=MetricStatus.UNKNOWN,
            ),
            volume=VolumeSnapshot(trend="unavailable", activity=VolumeActivity.NORMAL),
            volatility=VolatilitySnapshot(suitability=VolatilitySuitability.UNKNOWN),
            dominant_direction=ScannerDirection.NEUTRAL,
            timeframe_alignment="unavailable",
            alignment_ratio=0,
            technical_activity=TechnicalActivity.DORMANT,
            data_quality_status=status.value,
            warnings=[warning],
        )

    def _statistics(
        self,
        candidates: list[ScannerCandidate],
        started_at: datetime,
        completed_at: datetime,
        elapsed: float,
        api_requests: int,
        discovery_errors: int,
    ) -> ScannerStatistics:
        statuses = Counter(candidate.status for candidate in candidates)
        filters = Counter()
        for candidate in candidates:
            for warning in candidate.warnings:
                if warning.startswith("filtered_by_"):
                    filters[warning.split(":", 1)[0]] += 1
        if discovery_errors:
            filters["filtered_by_discovery"] += discovery_errors
        return ScannerStatistics(
            scan_started_at=started_at,
            scan_completed_at=completed_at,
            total_markets=len(candidates) + discovery_errors,
            eligible_markets=statuses[CandidateStatus.ELIGIBLE],
            filtered_markets=statuses[CandidateStatus.FILTERED],
            warning_markets=statuses[CandidateStatus.WARNING],
            data_errors=statuses[CandidateStatus.DATA_ERROR] + discovery_errors,
            stale_markets=statuses[CandidateStatus.STALE],
            insufficient_data_markets=statuses[CandidateStatus.INSUFFICIENT_DATA],
            processing_time_seconds=elapsed,
            average_processing_time_ms=(elapsed / len(candidates) * 1000 if candidates else 0),
            api_requests=api_requests,
            analysis_time_seconds=self._analysis_seconds,
            filter_counts=dict(filters),
        )
