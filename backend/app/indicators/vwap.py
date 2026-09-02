from datetime import UTC

from app.market_data.models import NormalizedCandle


def utc_session_vwap(candles: list[NormalizedCandle]) -> list[float | None]:
    """VWAP reset at each UTC calendar-day boundary using typical price."""
    output: list[float | None] = []
    session = None
    cumulative_volume = 0.0
    cumulative_value = 0.0
    for candle in candles:
        candle_session = candle.timestamp.astimezone(UTC).date()
        if candle_session != session:
            session = candle_session
            cumulative_volume = 0.0
            cumulative_value = 0.0
        typical_price = (candle.high + candle.low + candle.close) / 3
        cumulative_volume += candle.volume
        cumulative_value += typical_price * candle.volume
        output.append(cumulative_value / cumulative_volume if cumulative_volume > 0 else None)
    return output
