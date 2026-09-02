# Phase 9: live-market paper trading

Phase 9 consumes only normalized public CoinDCX ticker, trade, order-book, and candle data. The existing Phase 3–7 pipeline remains the sole source of analysis, scanning, scoring, setups, and risk decisions. `PaperTradeExecutor` is the only new execution adapter and cannot accept live mode or an exchange client.

## Safety boundary

- `TRADING_MODE` accepts only `paper`.
- No private CoinDCX client is imported by `app.paper_trading`.
- No exchange order, cancellation, TP/SL, position, balance, or account endpoint is called.
- Paper stop and target orders are internal PostgreSQL records.
- New positions require a `TRIGGERED` Phase 6 setup and an allowed Phase 7 decision.
- Missing or stale bid/ask data prevents entry. Existing positions remain persisted and monitoring resumes after recovery.

## Execution assumptions

The default `SLIPPAGE_ADJUSTED` model enters longs at the best ask and shorts at the best bid, then applies adverse configured entry slippage. Exits use the best bid for longs and best ask for shorts, followed by adverse exit slippage. Phase 8 fee and slippage formulas are reused. Entry and exit fees are recorded independently and deducted once.

Live trade/order-book events are preferred for TP/SL monitoring. The candle fallback is conservative: if both stop and target occur within one candle and ordering is unknown, stop is assumed first. Funding is marked `disabled` by default or `unavailable` when enabled without a normalized public funding stream; it is never fabricated.

## Persistence and recovery

Paper accounts, sessions, orders, positions, setups, trades, and the runtime recovery snapshot use dedicated PostgreSQL tables. A lifecycle save occurs in one database transaction. Startup restores the snapshot, recalculates account values, rejects orphaned filled entries, and quarantines duplicate open positions rather than creating new exposure.

Reset requires the exact phrase `RESET PAPER TRADING` and refuses while positions are open. Historical sessions are retained.

## API and UI

The project convention is `/api/v1`, so Phase 9 endpoints are under `/api/v1/paper`. The `/paper` page always displays `MODE: PAPER · NO REAL ORDERS`, current account/risk/health state, simulated positions and trades, performance charts, backtest comparison, drift warnings, and a two-stage reset control.

Performance drift is descriptive only. Fewer than the configured minimum number of completed paper trades produces `INSUFFICIENT_SAMPLE`; drift never disables trading by itself.
