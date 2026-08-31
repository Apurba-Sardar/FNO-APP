from app.domain.market import OrderBook, OrderBookMetrics


class InsufficientDepthError(ValueError):
    pass


def estimate_slippage_bps(levels: list[tuple[float, float]], quote_notional: float) -> float:
    if quote_notional <= 0:
        raise ValueError("quote_notional must be positive")
    remaining = quote_notional
    acquired = 0.0
    best = levels[0][0] if levels else 0.0
    for price, quantity in levels:
        consumed = min(remaining, price * quantity)
        acquired += consumed / price
        remaining -= consumed
        if remaining <= 1e-9:
            break
    if remaining > 1e-9 or acquired == 0 or best == 0:
        raise InsufficientDepthError("order book cannot fill requested notional")
    average = quote_notional / acquired
    return abs(average - best) / best * 10_000


def analyze_order_book(
    book: OrderBook, depth_window_bps: float = 50, test_notional: float = 1_000, side: str = "buy"
) -> OrderBookMetrics:
    if not book.bids or not book.asks:
        raise InsufficientDepthError("empty order book")
    if any(price <= 0 or quantity <= 0 for price, quantity in book.bids + book.asks):
        raise ValueError("order book contains non-positive levels")
    best_bid, best_ask = book.bids[0][0], book.asks[0][0]
    if best_bid >= best_ask:
        raise ValueError("order book is locked or crossed")
    midpoint = (best_bid + best_ask) / 2
    bid_floor = midpoint * (1 - depth_window_bps / 10_000)
    ask_ceiling = midpoint * (1 + depth_window_bps / 10_000)
    bids = [(p, q) for p, q in book.bids if p >= bid_floor]
    asks = [(p, q) for p, q in book.asks if p <= ask_ceiling]
    bid_volume = sum(q for _, q in bids)
    ask_volume = sum(q for _, q in asks)
    total = bid_volume + ask_volume
    levels = book.asks if side == "buy" else book.bids
    return OrderBookMetrics(
        bid_volume=bid_volume,
        ask_volume=ask_volume,
        imbalance=0 if not total else (bid_volume - ask_volume) / total,
        spread_bps=(best_ask - best_bid) / midpoint * 10_000,
        execution_depth_quote=sum(p * q for p, q in bids + asks),
        estimated_slippage_bps=estimate_slippage_bps(levels, test_notional),
    )
