from datetime import UTC, datetime

import pytest

from app.domain.market import OrderBook
from app.market_data.orderbook import (
    InsufficientDepthError,
    analyze_order_book,
    estimate_slippage_bps,
)


def test_order_book_metrics():
    book = OrderBook(
        pair="B-BTC_USDT",
        timestamp=datetime.now(UTC),
        bids=[(99, 20), (98, 20)],
        asks=[(101, 10), (102, 10)],
    )
    result = analyze_order_book(book, depth_window_bps=300, test_notional=1500)
    assert result.spread_bps == pytest.approx(200)
    assert result.bid_volume == 40
    assert result.ask_volume == 20
    assert result.estimated_slippage_bps > 0


def test_slippage_rejects_insufficient_depth():
    with pytest.raises(InsufficientDepthError):
        estimate_slippage_bps([(100, 1)], 101)


def test_crossed_order_book_is_rejected_as_abnormal():
    book = OrderBook(
        pair="B-BTC_USDT",
        timestamp=datetime.now(UTC),
        bids=[(102, 1)],
        asks=[(101, 1)],
    )
    with pytest.raises(ValueError, match="crossed"):
        analyze_order_book(book, test_notional=50)
