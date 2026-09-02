from datetime import UTC, datetime

from app.indicators.models import MultiTimeframeAnalysis, TrendState
from app.market_data.models import OrderBookSnapshot

from .config import ScannerConfig
from .models import (
    LiquidityClassification,
    LiquiditySnapshot,
    MetricStatus,
    ScannerDirection,
    TechnicalActivity,
    VolatilitySnapshot,
    VolatilitySuitability,
    VolumeActivity,
    VolumeSnapshot,
)


def spread_percent(book: OrderBookSnapshot) -> float | None:
    if not book.bids or not book.asks:
        return None
    best_bid, best_ask = book.bids[0][0], book.asks[0][0]
    midpoint = (best_bid + best_ask) / 2
    if midpoint <= 0 or best_bid <= 0 or best_ask <= best_bid:
        return None
    return (best_ask - best_bid) / midpoint * 100


def estimate_slippage_percent(levels: list[tuple[float, float]], notional: float) -> float | None:
    if notional <= 0 or not levels or levels[0][0] <= 0:
        return None
    remaining = notional
    base_quantity = 0.0
    best_price = levels[0][0]
    for price, quantity in levels:
        if price <= 0 or quantity <= 0:
            return None
        consumed = min(remaining, price * quantity)
        base_quantity += consumed / price
        remaining -= consumed
        if remaining <= 1e-9:
            break
    if remaining > 1e-9 or base_quantity <= 0:
        return None
    average_price = notional / base_quantity
    return abs(average_price - best_price) / best_price * 100


def analyze_liquidity(
    book: OrderBookSnapshot | None, config: ScannerConfig, *, now: datetime | None = None
) -> LiquiditySnapshot:
    if book is None:
        return LiquiditySnapshot(
            classification=LiquidityClassification.UNUSABLE,
            spread_status=MetricStatus.UNKNOWN,
            slippage_status=MetricStatus.UNKNOWN,
        )
    current = now or datetime.now(UTC)
    if (current - book.timestamp).total_seconds() > config.max_orderbook_age_seconds:
        return LiquiditySnapshot(
            classification=LiquidityClassification.UNUSABLE,
            spread_status=MetricStatus.UNKNOWN,
            slippage_status=MetricStatus.UNKNOWN,
            orderbook_timestamp=book.timestamp,
        )
    spread = spread_percent(book)
    buy_slippage = estimate_slippage_percent(book.asks, config.intended_notional)
    sell_slippage = estimate_slippage_percent(book.bids, config.intended_notional)
    slippage = (
        max(buy_slippage, sell_slippage)
        if buy_slippage is not None and sell_slippage is not None
        else None
    )
    bid_depth = sum(price * quantity for price, quantity in book.bids)
    ask_depth = sum(price * quantity for price, quantity in book.asks)
    depth = min(bid_depth, ask_depth)
    if (
        spread is None
        or slippage is None
        or spread > config.max_spread_percent
        or slippage > config.max_slippage_percent
    ):
        classification = LiquidityClassification.UNUSABLE
    elif depth < config.acceptable_depth_quote:
        classification = LiquidityClassification.POOR
    elif (
        spread <= config.excellent_spread_percent
        and slippage <= config.excellent_slippage_percent
        and depth >= config.excellent_depth_quote
    ):
        classification = LiquidityClassification.EXCELLENT
    elif (
        spread <= config.good_spread_percent
        and slippage <= config.good_slippage_percent
        and depth >= config.good_depth_quote
    ):
        classification = LiquidityClassification.GOOD
    else:
        classification = LiquidityClassification.ACCEPTABLE
    return LiquiditySnapshot(
        classification=classification,
        spread_status=MetricStatus.KNOWN if spread is not None else MetricStatus.UNKNOWN,
        spread_percent=spread,
        slippage_status=MetricStatus.KNOWN if slippage is not None else MetricStatus.UNKNOWN,
        estimated_slippage_percent=slippage,
        bid_depth_quote=bid_depth,
        ask_depth_quote=ask_depth,
        orderbook_timestamp=book.timestamp,
    )


def classify_volume(
    current_volume: float | None,
    volume_ma: float | None,
    relative_volume: float | None,
    trend: str,
    config: ScannerConfig,
) -> VolumeSnapshot:
    activity = (
        VolumeActivity.NORMAL
        if relative_volume is None
        else VolumeActivity.EXTREME
        if relative_volume >= config.extreme_relative_volume
        else VolumeActivity.HIGH_ACTIVITY
        if relative_volume >= config.high_activity_relative_volume
        else VolumeActivity.ACTIVE
        if relative_volume >= config.active_relative_volume
        else VolumeActivity.QUIET
        if relative_volume < config.quiet_relative_volume
        else VolumeActivity.NORMAL
    )
    return VolumeSnapshot(
        current_volume=current_volume,
        volume_ma=volume_ma,
        relative_volume=relative_volume,
        trend=trend,
        activity=activity,
        spike=relative_volume is not None
        and relative_volume >= config.high_activity_relative_volume,
    )


def classify_volatility(
    atr: float | None,
    atr_percent: float | None,
    range_expansion: float | None,
    regime: str | None,
    config: ScannerConfig,
) -> VolatilitySnapshot:
    suitability = (
        VolatilitySuitability.UNKNOWN
        if atr_percent is None
        else VolatilitySuitability.TOO_LOW
        if atr_percent < config.minimum_atr_percent
        else VolatilitySuitability.EXTREME
        if atr_percent >= config.extreme_atr_percent
        else VolatilitySuitability.HIGH
        if atr_percent >= config.high_atr_percent
        else VolatilitySuitability.SUITABLE
    )
    return VolatilitySnapshot(
        atr=atr,
        atr_percent=atr_percent,
        recent_range_expansion=range_expansion,
        regime=regime,
        suitability=suitability,
    )


def classify_direction(analysis: MultiTimeframeAnalysis) -> ScannerDirection:
    bullish = analysis.alignment.bullish_count
    bearish = analysis.alignment.bearish_count
    if bullish and bearish:
        return ScannerDirection.MIXED
    if bullish > bearish and analysis.alignment.alignment_ratio > 0.5:
        return ScannerDirection.BULLISH
    if bearish > bullish and analysis.alignment.alignment_ratio > 0.5:
        return ScannerDirection.BEARISH
    if any(item.trend == TrendState.TRANSITION for item in analysis.timeframes.values()):
        return ScannerDirection.MIXED
    return ScannerDirection.NEUTRAL


def classify_technical_activity(
    analysis: MultiTimeframeAnalysis,
    volume: VolumeSnapshot,
    volatility: VolatilitySnapshot,
) -> TechnicalActivity:
    points = 0
    if volume.activity in {
        VolumeActivity.ACTIVE,
        VolumeActivity.HIGH_ACTIVITY,
        VolumeActivity.EXTREME,
    }:
        points += 1
    if volatility.suitability in {VolatilitySuitability.SUITABLE, VolatilitySuitability.HIGH}:
        points += 1
    if volatility.recent_range_expansion is not None and volatility.recent_range_expansion >= 1.2:
        points += 1
    if analysis.alignment.alignment_ratio >= 0.5:
        points += 1
    lower_frames = [
        item
        for timeframe, item in analysis.timeframes.items()
        if timeframe.value in {"1h", "15m", "5m"}
    ]
    if any(
        item.momentum and item.momentum.price_momentum in {"positive", "negative"}
        for item in lower_frames
    ):
        points += 1
    return (
        TechnicalActivity.HIGH_ACTIVITY
        if points >= 4
        else TechnicalActivity.ACTIVE
        if points >= 2
        else TechnicalActivity.NORMAL
        if points == 1
        else TechnicalActivity.DORMANT
    )
