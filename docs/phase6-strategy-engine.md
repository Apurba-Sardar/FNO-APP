# Phase 6 deterministic strategy engine

Phase 6 is an analysis-only layer between opportunity ranking and future risk/execution
phases. It has no CoinDCX client, account API, order API, quantity, leverage, or execution
dependency. `TRIGGERED` means that a completed candle met deterministic analytical rules;
it is not an instruction to trade.

## Point-in-time convention

Every evaluation receives an explicit timezone-aware `evaluation_timestamp`. A candle is
eligible only when `candle.timestamp + timeframe_duration <= evaluation_timestamp`. This
treats CoinDCX candle timestamps as interval-open timestamps and prevents the current or a
future candle from influencing a decision. EMA, VWAP, ATR, volume, structure, support, and
resistance are recomputed from that closed subset. A market/order-book snapshot timestamped
after the evaluation time fails the data gate.

## Trend pullback

The analytical direction comes from the Phase 5 long/short evidence. Daily and 4h trend must
agree; 1h may agree, be neutral, or transition, but may not oppose. The 15m structure must
remain intact. The entry area is centered on the mean of available 15m EMA20 and UTC-session
VWAP with a configurable ATR half-width. A trigger requires a completed 5m close through the
prior configurable swing window, a directional candle body, minimum body/range ratio, and
relative-volume confirmation.

## Breakout

The prior configurable 15m window defines the consolidation high and low. Its width is bounded
in ATR units. A high/low wick through the boundary is insufficient: the completed candle must
close beyond it, have a directional body, acceptable adverse wick, relative-volume expansion,
and a breakout distance inside configurable ATR bounds. Optional retest enforcement is reserved
in configuration but disabled initially.

## Hypothetical levels

Stops are anchored to nearby Phase 3 swing structure plus a configurable ATR buffer and must
fall inside minimum/maximum ATR-distance bounds. Breakout invalidation is the reclaimed range
boundary plus that buffer. Targets prefer the configured R multiple but are capped at the first
nearby opposing Phase 3 level. `risk_reward = abs(target-entry) / abs(entry-stop)`; the hard
minimum defaults to 1.5. These values are analysis data only.

## Setup quality and lifecycle

The 0–100 quality measure is the weighted sum of ten auditable inputs: trend alignment,
structure, entry location, trigger quality, volume, momentum, liquidity, volatility, target room,
and risk/reward. Weights total 100. It is not a win probability. Classifications are excellent
(90+), good (80–89), acceptable (70–79), weak (60–69), and invalid (below 60). These
thresholds are centralized and configurable.

Lifecycle states are `NO_SETUP`, `WATCH`, `ARMED`, `TRIGGERED`, `INVALIDATED`, and `EXPIRED`.
Prior watch/armed/triggered records are invalidated by a completed close through their
invalidation price; untriggered records expire after the configured UTC validity window.

## Defaults and assumptions

- Minimum Phase 5 opportunity score: 50. This permits evaluation of the current live Phase 5
  score distribution while all liquidity and risk/reward hard gates remain mandatory.
- Minimum quality: 60; minimum R:R: 1.5; preferred R:R: 2.0.
- Setups expire after 60 minutes and data older than 30 minutes is rejected.
- The engine evaluates at most the top 25 eligible opportunities per automatic batch.
- Redis stores only the latest TTL-bounded setup snapshot; candles remain the source data.
