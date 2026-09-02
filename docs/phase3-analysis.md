# Phase 3 quantitative analysis conventions

Phase 3 is deterministic, read-only analysis. It does not produce orders, trade scores,
position sizes, profit probabilities, or long/short recommendations.

## Indicator definitions

- EMA uses an SMA seed at the first complete period, then `alpha = 2 / (period + 1)`.
  Periods are 20, 50, and 200.
- RSI(14) uses Wilder smoothing. A flat series is reported as 50; insufficient history is null.
- MACD uses EMA(12) minus EMA(26), with an EMA(9) signal line. Crossovers compare the two most
  recent valid MACD/signal pairs.
- ATR(14) uses true range and Wilder smoothing. ATR percent is `ATR / close * 100`.
- VWAP uses typical price `(high + low + close) / 3`, weighted by candle volume. It resets at
  every UTC calendar-day boundary. A session with no volume returns null.
- Volume MA defaults to 20 periods. Relative volume is `current volume / volume MA`; a zero
  average returns null. Values of 1.5 and 2.0 classify elevated volume and a strong spike.
- ROC defaults to 5 and 10 periods and is reported as percentage change.

## Structure and levels

A swing high must be strictly higher than every high in the configured number of candles on
both sides. Swing lows use the corresponding strict-low rule. The default window is three.
Two increasing swing highs/lows describe bullish structure; two decreasing swing highs/lows
describe bearish structure. Other combinations remain neutral.

Nearby swing points are clustered using a configurable percentage tolerance. Cluster size is
reported as strength. Levels are explicitly labelled `potential_support` or
`potential_resistance`; they are descriptive areas, not guarantees.

## Trend, alignment, and volatility

A timeframe is bullish only when price is above EMA20, EMA20 is above EMA50, and recent
structure is bullish. The bearish rule is the inverse. Contradictory EMA and structure evidence
is transition; incomplete or unaligned evidence is neutral. Trend strength is a 0–100 alignment
measure from available EMA position/alignment, structure, EMA slope, and RSI evidence. It is not
a probability or forecast.

Multi-timeframe alignment counts bullish, bearish, neutral, and transition states across the
requested 1w, 1d, 4h, 1h, 15m, and 5m frames. At least 80% directional agreement is strong;
more than 50% is directional; everything else is mixed.

Volatility uses ATR percent thresholds from centralized indicator configuration: below 0.5% is
low, 0.5%–2% normal, 2%–4% high, and at least 4% extreme. Range expansion compares the average
percentage range of the latest five candles with the preceding twenty.

## Time and data quality

All timestamps are timezone-aware UTC. Inputs are checked for ordering, duplicates, timeframe
mismatches, unexpected gaps, staleness, and the 200 candles required for complete EMA coverage.
Unavailable indicators remain null. Analysis completeness measures data availability and quality
only; it is not a trading-confidence or win-probability value.

## Performance baseline

`backend/scripts/benchmark_analysis.py` constructs 100 symbols × 6 timeframes × 220 candles.
On the Phase 3 development machine (Windows, Python 3.13), the measured untraced analysis pass
was 2.0407 seconds for 600 timeframe analyses. With `tracemalloc` enabled, the first and repeated
passes were 15.8480 and 13.7397 seconds. Fixture memory was 157.5322 MiB and traced peak memory
was 157.7430 MiB, so the incremental peak observed during analysis was approximately 0.21 MiB.
The initial development baseline is therefore no more than 3 seconds for the untraced synthetic
batch on comparable hardware. This is a regression baseline, not a production latency SLA.
