# Phase 8 historical backtesting

Phase 8 validates the existing deterministic analytical pipeline against normalized PostgreSQL
candles. It is isolated from live scanner/risk Redis keys, authenticated CoinDCX APIs, orders,
positions, and paper execution.

## Time convention and warmup

Normalized candle timestamps are candle-open times. A candle is accessible only when
`open timestamp + timeframe duration <= evaluation timestamp`. The historical context enforces
this for 1w, 1d, 4h, 1h, 15m, and 5m data. Each timeframe loads up to 220 stored candles before the
requested start by default. Warmup candles are available to indicators but excluded from simulated
performance events.

Missing candles are reported and never forward-filled. The default `SKIP_PERIOD` policy continues
with available timestamps; `ABORT_SYMBOL` fails the run if gaps are present. Invalid or duplicate
candles always fail validation.

## Event and execution rules

Portfolio events are processed in stable `(close timestamp, symbol)` order. Existing positions are
updated first, delayed entry attempts are processed next, and new Phase 5/6/7 evaluations occur
last. A setup cannot fill earlier than the next 5m candle.

The default execution assumptions are:

- market execution;
- 5 bps adverse entry and exit slippage;
- 0.05% taker fee per side;
- 0.05% historical spread assumption when order-book history is unavailable;
- stop-first when both stop and target occur in one OHLC candle;
- adverse candle open for gaps through a stop;
- 240-minute time exit;
- close remaining positions at the final available price.

All assumptions are serialized in the run configuration. Fees and positive slippage costs cannot
improve P&L. Funding is excluded and warned because no historical funding series is stored. The
system never fabricates order-book depth or funding payments.

## Reused engines

Historical candles are adapted into the existing normalized `ScannerCandidate` interface. Phase 5
`OpportunityScoringEngine`, Phase 6 `StrategyEngine`, and Phase 7 `RiskEngine` are called directly.
There is no backtest-specific strategy or position-sizing formula. Missing Phase 2 instrument
constraints cause Phase 7 rejection; explicit normalized instrument overrides may be included in a
configuration snapshot for reproducible research.

Historical market-universe and order-book metadata are incomplete in the current database. The
report flags this limitation. The backtester must not interpret today's eligibility as proof that a
contract existed historically.

## Analytics and robustness

Results contain full trades and lifecycle transitions, equity/drawdown curves, execution totals,
daily/monthly output, and strategy, direction, symbol, regime, opportunity-score, and setup-score
breakdowns. Results warn when fewer than 30 trades are available.

Explicit scenarios cover baseline, doubled fees/slippage, lower fees, wider assumed spread, delayed
entry, and conservative intrabar order. Parameter sensitivity returns every requested variant and
never selects a winner. Walk-forward utilities maintain separate in-sample and out-of-sample
windows. Optional seeded Monte Carlo shuffles observed trade order only and is labeled as uncertainty
simulation, not prediction.

## API

The `/api/v1/backtests` namespace supports create/list/detail/run, trades, equity, drawdown,
configuration, and HTML reports. Runs are persisted under the separate `backtest:results` Redis
hash. These endpoints cannot place or alter trades.
