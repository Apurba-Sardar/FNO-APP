# Phase 4 all-market scanner

Phase 4 discovers the active USDT futures universe dynamically and creates diagnostic scanner
candidates. It does not rank candidates, recommend trades, or call authenticated endpoints.

## Pipeline and classifications

Cheap checks run first: active status, one cycle-wide current-price snapshot, ticker freshness and
24-hour volume, then public order-book spread/depth/slippage. Only viable markets load six candle
frames and enter the Phase 3 analyzer.

Spread is `(best ask - best bid) / midpoint * 100`. Slippage walks documented order-book levels
for the configured notional and compares volume-weighted average execution with the best price.
It is an estimate. Missing or insufficient depth remains unknown; `unknown_liquidity_eligible`
controls whether that state is filtered.

Liquidity thresholds are centralized in `ScannerConfig`. Excellent, good, and acceptable require
progressively wider spread/slippage and lower two-sided quote depth. Poor means fillable but below
minimum desired depth. Unusable includes crossed/empty/stale books, excessive spread/slippage, or
an unfillable test notional.

Volume activity uses Phase 3 relative volume: below 0.75 quiet, 0.75–1.5 normal, 1.5–2 active,
2–3 high activity, and at least 3 extreme. Volatility suitability uses 15-minute ATR percent:
below 0.10 too low, 0.10–2.5 suitable, 2.5–5 high, and at least 5 extreme. Every threshold is
configurable through nested environment settings.

Technical activity combines relative volume, suitable/high volatility, range expansion,
timeframe alignment, and lower-frame price momentum. It answers whether a market warrants later
inspection; it is not a directional trade signal. Direction remains bullish, bearish, mixed, or
neutral and never uses long/short terminology.

## Runtime safety

The scanner uses bounded async concurrency and the existing centralized CoinDCX request throttle.
A process-local lock rejects overlapping full cycles. APScheduler uses `max_instances=1` and
coalescing. Redis stores only the latest candidate/state set with a TTL and the in-memory state
continues working when Redis is unavailable. Setting `MARKET_SCANNER__CONTROL_TOKEN` protects POST
run/start/stop endpoints through the `X-Scanner-Control-Token` header; the token is never returned.

## Synthetic performance baseline

Run `python scripts/benchmark_scanner.py` from `backend` to exercise the real scanner analysis
path with deterministic in-memory data. On the 2026-08-31 development run, 100 markets × six
timeframes × 220 candles completed in 21.4214 seconds with five concurrent workers, 21.3270
seconds attributed to analysis, 214.2137 ms wall-clock time per symbol, 702 simulated public
requests, and zero failed symbols. The generated fixtures occupied 157.5766 MiB and traced peak
memory was 167.9681 MiB. These figures are a development baseline, not a production target;
Python analysis CPU and retaining the complete synthetic fixture universe were the bottlenecks.
