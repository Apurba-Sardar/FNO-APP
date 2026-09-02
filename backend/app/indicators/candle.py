from app.market_data.models import NormalizedCandle

from .models import CandleCharacteristics


def characterize(candle: NormalizedCandle) -> CandleCharacteristics:
    total_range = candle.high - candle.low
    body = abs(candle.close - candle.open)
    upper_wick = candle.high - max(candle.open, candle.close)
    lower_wick = min(candle.open, candle.close) - candle.low
    ratio = body / total_range if total_range else None
    close_location = (candle.close - candle.low) / total_range if total_range else None
    direction = (
        "bullish"
        if candle.close > candle.open
        else "bearish"
        if candle.close < candle.open
        else "flat"
    )
    doji = ratio is not None and ratio <= 0.1
    strong_bullish = (
        direction == "bullish" and ratio is not None and ratio >= 0.7 and close_location >= 0.8
    )
    strong_bearish = (
        direction == "bearish" and ratio is not None and ratio >= 0.7 and close_location <= 0.2
    )
    rejection = None
    if total_range and upper_wick >= max(body * 2, total_range * 0.5):
        rejection = "upper"
    elif total_range and lower_wick >= max(body * 2, total_range * 0.5):
        rejection = "lower"
    return CandleCharacteristics(
        body_size=body,
        upper_wick=max(0, upper_wick),
        lower_wick=max(0, lower_wick),
        total_range=total_range,
        body_range_ratio=ratio,
        direction=direction,
        close_location=close_location,
        doji=doji,
        strong_bullish=strong_bullish,
        strong_bearish=strong_bearish,
        rejection_wick=rejection,
    )
