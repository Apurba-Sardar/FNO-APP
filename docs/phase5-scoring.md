# Phase 5 opportunity scoring

Phase 5 converts immutable Phase 4 scanner candidates into deterministic analytical rankings.
It does not create a trade signal, executable price, order, position size, leverage, stop, or target.
An opportunity score describes setup quality for further strategy evaluation; it is not a
probability of profit.

## Reproducible calculation

Each of the ten factors is normalized to 0–100. Its contribution is
`normalized_score × configured_weight / 100`; the ten default weights total 100. Both bullish
and bearish cases are calculated from the same functions. Trend direction, strength, structure,
EMA relationships, price/EMA position, momentum state, ROC, VWAP, relative volume, spread,
estimated slippage, depth, ATR suitability, and nearby potential levels remain in each factor's
`raw_value` audit record.

Weekly, daily, and 4h factors combine trend, trend strength, EMA alignment, price position, and
structure. Daily/4h disagreement applies a deterministic conflict penalty. The 1h factor combines
RSI state, MACD state, price momentum, EMA alignment, ROC, and range expansion. RSI overbought or
oversold state is never treated as a standalone reversal instruction. The 15m factor describes
technical cleanliness from trend, structure, momentum, EMA/VWAP position, and volume.

Volume classifications map to a bounded suitability score; extreme activity is deliberately not
maximal. Liquidity combines the Phase 4 class with measured spread and estimated slippage.
Volatility rewards suitable movement, gives high volatility a lower score, and penalizes too-low,
extreme, or unknown conditions.

## Structural room

Estimated structural R:R requires both a potential support below price and potential resistance
above price from the 15m Phase 3 structure. Directional risk uses the greater of structure distance
and the configured ATR multiple; reward uses room to the nearest opposing potential level. If the
two-sided structure or valid ATR is unavailable, R:R is null. This is an analytical room estimate,
not an executable stop or target.

## Direction and gates

The larger directional score supplies opportunity score. If bullish and bearish scores differ by
less than the configured threshold, direction is neutral or mixed; otherwise it is bullish or
bearish. These terms describe analytical evidence and are not trade instructions.

Hard gates override score acceptance for non-eligible Phase 4 status, stale or invalid prices,
liquidity below the configured minimum, unknown/excessive spread, extreme volatility when enabled,
critical data quality, missing timeframes, or invalid/stale timeframe analysis. A gated opportunity
has final opportunity score zero and remains available for diagnostics.

Default tiers are A+ at 90, A at 80, B at 70, C at 60, and D below 60. Ranking is deterministic:
opportunity score, liquidity quality, data quality, estimated structural R:R, then symbol.

## State and performance

Only the current opportunity set and statistics are cached in Redis with a TTL. Each calculation
tracks previous score/rank and their changes without smoothing. Scanner completion invokes scoring
through a composition callback; the Phase 4 scanner package does not import scoring.

The 2026-09-01 synthetic benchmark of 100 candidates × six timeframes × ten factors per direction
completed scoring in 0.220086 seconds (2.200864 ms/market). Ranking took 0.002338 seconds and traced
peak memory was 3.763201 MiB. These local development measurements are a baseline, not a production
guarantee.
