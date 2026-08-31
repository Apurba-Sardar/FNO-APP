from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from pydantic import ValidationError

from app.domain.market import Timeframe
from app.services.coindcx.models import (
    CoinDCXCandle,
    CoinDCXInstrument,
    CoinDCXOrderBook,
    WebSocketCandle,
    WebSocketTrade,
)

from .models import (
    CandleResult,
    CandleValidationIssue,
    Market,
    MarketTrade,
    MarketType,
    NormalizedCandle,
    OrderBookSnapshot,
    Ticker,
)

TIMEFRAME_DURATION = {
    Timeframe.MINUTE_5: timedelta(minutes=5),
    Timeframe.MINUTE_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOUR_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
    Timeframe.WEEK_1: timedelta(weeks=1),
}


def epoch_milliseconds(value: Any) -> datetime:
    if value is None:
        raise ValueError("missing millisecond timestamp")
    timestamp = float(value)
    if timestamp <= 0:
        raise ValueError("invalid millisecond timestamp")
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC)


def epoch_seconds(value: Any) -> datetime:
    if value is None:
        raise ValueError("missing second timestamp")
    timestamp = float(value)
    if timestamp <= 0:
        raise ValueError("invalid second timestamp")
    return datetime.fromtimestamp(timestamp, tz=UTC)


def precision_from_increment(value: float | None) -> int | None:
    if value is None or value <= 0:
        return None
    return max(0, -Decimal(str(value)).normalize().as_tuple().exponent)


def normalize_market(raw: CoinDCXInstrument) -> Market:
    return Market(
        symbol=raw.pair,
        base_asset=raw.underlying_currency_short_name or raw.pair.split("_")[0].removeprefix("B-"),
        quote_asset=raw.quote_currency_short_name,
        market_type=MarketType.FUTURES,
        status=raw.status.lower(),
        contract_kind=raw.kind,
        price_precision=precision_from_increment(raw.price_increment),
        quantity_precision=precision_from_increment(raw.quantity_increment),
        min_quantity=raw.min_quantity,
        min_notional=raw.min_notional,
        tick_size=raw.price_increment,
        step_size=raw.quantity_increment,
    )


def normalize_active_symbol(symbol: str) -> Market:
    prefix, separator, quote = symbol.partition("_")
    if not separator:
        raise ValueError("invalid CoinDCX futures pair")
    return Market(
        symbol=symbol,
        base_asset=prefix.removeprefix("B-"),
        quote_asset=quote,
        market_type=MarketType.FUTURES,
        status="active",
    )


def normalize_rest_candles(
    symbol: str,
    timeframe: Timeframe,
    rows: list[CoinDCXCandle],
    *,
    now: datetime | None = None,
) -> CandleResult:
    issues: list[CandleValidationIssue] = []
    candles: list[NormalizedCandle] = []
    seen: set[datetime] = set()
    for index, row in enumerate(rows):
        try:
            timestamp = epoch_milliseconds(row.time)
            if timestamp in seen:
                raise ValueError("duplicate timestamp")
            candle = NormalizedCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            seen.add(timestamp)
            candles.append(candle)
        except (TypeError, ValueError, ValidationError) as exc:
            issue = CandleValidationIssue(
                index=index,
                timestamp=None if row.time is None else str(row.time),
                reason=str(exc),
            )
            issues.append(issue)
            structlog.get_logger().warning(
                "CANDLE_VALIDATION_ERROR",
                symbol=symbol,
                timeframe=timeframe.value,
                **issue.model_dump(),
            )
    candles.sort(key=lambda item: item.timestamp)
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    stale = not candles or reference - candles[-1].timestamp > TIMEFRAME_DURATION[timeframe] * 2
    if stale:
        issues.append(CandleValidationIssue(reason="latest candle is stale"))
    return CandleResult(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        validation_issues=issues,
        stale=stale,
    )


def normalize_websocket_candle(payload: dict) -> NormalizedCandle:
    outer = payload.get("data", payload)
    rows = outer.get("data") if isinstance(outer, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("malformed candlestick WebSocket message")
    raw = WebSocketCandle.model_validate(rows[0])
    return NormalizedCandle(
        symbol=raw.pair,
        timeframe=Timeframe(raw.duration.lower()),
        timestamp=epoch_seconds(raw.open_time),
        open=raw.open,
        high=raw.high,
        low=raw.low,
        close=raw.close,
        volume=raw.volume,
    )


def normalize_websocket_trade(payload: dict) -> MarketTrade:
    raw = WebSocketTrade.model_validate(payload.get("data", payload))
    return MarketTrade(
        symbol=raw.s,
        timestamp=epoch_milliseconds(raw.T),
        price=raw.p,
        quantity=raw.q,
        buyer_is_maker=bool(raw.m),
    )


def normalize_websocket_orderbook(symbol: str, payload: dict) -> OrderBookSnapshot:
    raw = CoinDCXOrderBook.model_validate(payload.get("data", payload))
    return OrderBookSnapshot(
        symbol=symbol,
        timestamp=epoch_milliseconds(raw.ts),
        bids=sorted(((float(p), float(q)) for p, q in raw.bids.items()), reverse=True),
        asks=sorted((float(p), float(q)) for p, q in raw.asks.items()),
        version=raw.vs,
    )


def normalize_tickers(payload: dict) -> list[Ticker]:
    data = payload.get("data", payload)
    timestamp = epoch_milliseconds(data.get("ts"))
    prices = data.get("prices")
    if not isinstance(prices, dict):
        raise TypeError("malformed current prices WebSocket message")
    result = []
    for symbol, values in prices.items():
        if not isinstance(values, dict):
            continue
        result.append(
            Ticker(
                symbol=symbol,
                timestamp=timestamp,
                last_price=values.get("ls"),
                mark_price=values.get("mp"),
                high_24h=values.get("h"),
                low_24h=values.get("l"),
                volume_24h=values.get("v"),
                price_change_percent=values.get("pc"),
            )
        )
    return result
