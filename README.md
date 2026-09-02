# CoinDCX USDT Futures Scalping System

Phase 9 of a deterministic, safety-first futures system. The application provides public CoinDCX market data, quantitative analysis, scanning, scoring, strategy/risk evaluation, historical validation, and durable live-market paper simulation. It contains no live-order implementation or private trading API.

The paper dashboard is available at `/paper`. `TRADING_MODE=paper` is the only accepted execution mode. See [Phase 9 documentation](docs/phase9-paper-trading.md).

## Included through Phase 9

- Next.js/TypeScript/Tailwind dashboard shell with shadcn-style primitives
- FastAPI backend with typed environment configuration and structured JSON logging
- PostgreSQL models for instruments, candles, scan runs, opportunities, trades, orders, and system events
- Redis/PostgreSQL development services in Docker Compose
- Documented CoinDCX public futures client with bounded retry/backoff
- USDT futures discovery, candles, deterministic timeframe aggregation, and order-book analytics
- One reusable indicator engine: EMA 20/50/200, RSI, MACD, ATR, VWAP, volume average, relative volume, swings, support/resistance
- Multi-timeframe analysis, configurable 0–100 scoring, and hard pre-score market filters
- Unit and mocked integration tests; no real credentials
- Isolated CoinDCX REST and public Socket.IO clients in `backend/app/services/coindcx`
- Centralized 16-request/second-safe throttling, timeout handling, 429 handling, and exponential retry
- Normalized markets, candles, tickers, trades, and order-book snapshots
- Candle validation, per-symbol error isolation, PostgreSQL duplicate prevention, and Redis caching
- Public futures WebSocket reconnect, stale detection, resubscription, and graceful shutdown
- Read-only market-data, multi-timeframe, ticker, and health endpoints
- Developer validation page at `http://localhost:3000/market-data`
- Typed Phase 3 EMA, RSI, MACD, ATR, UTC-session VWAP, volume, candle, structure,
  support/resistance, momentum, volatility, trend, and alignment analysis
- Explicit data-quality and analysis-completeness reporting with null unavailable values
- Dynamic all-market scanner with cheap-first filters, bounded concurrency, and per-symbol failure isolation
- Configurable spread, order-book depth/slippage, volume, volatility, and technical-activity classifications
- Redis-backed latest scanner state, non-overlapping APScheduler cycles, and manual scanner controls
- Searchable/sortable scanner and analysis-only candidate detail pages at `http://localhost:3000/scanner`
- Direction-aware 0–100 opportunity scoring with ten normalized, configurable factors
- Deterministic hard gates, explanations, tiers, stable tie-breaking, and score/rank change tracking
- Ranked opportunities and complete factor-audit pages at `http://localhost:3000/opportunities`
- Independent trend-pullback and breakout analyzers with closed-candle anti-lookahead rules
- Auditable hypothetical entry, invalidation, target, R:R, quality, and lifecycle models
- Read-only setup API and charted developer pages at `http://localhost:3000/setups`
- Central deterministic all-in loss budgeting, position sizing, exposure, leverage, margin,
  daily-loss, consecutive-loss, and market-quality risk guards
- Redis-backed restart-safe risk state, explainable decisions, and Risk Center at
  `http://localhost:3000/risk`
- Database-first, point-in-time historical backtester with conservative fills, fees, slippage,
  portfolio accounting, reproducible reports, robustness utilities, and Backtesting Lab at
  `http://localhost:3000/backtests`

## Run locally

```bash
copy .env.example .env
docker compose up --build
```

API docs: `http://localhost:8000/docs`; dashboard: `http://localhost:3000`.

Read-only market-data and Phase 3 analysis endpoints:

- `GET /api/v1/markets`
- `GET /api/v1/markets/{symbol}/candles?timeframe=15m&limit=200`
- `GET /api/v1/markets/{symbol}/multi-timeframe?limit=200`
- `GET /api/v1/markets/{symbol}/ticker`
- `GET /api/v1/health/market-data`
- `GET /api/v1/analysis/{symbol}`
- `GET /api/v1/analysis/{symbol}?timeframes=1W,1D,4H,1H,15m,5m`
- `GET /api/v1/analysis/{symbol}/{timeframe}`
- `GET /api/v1/scanner/status`
- `GET /api/v1/scanner/candidates`
- `GET /api/v1/scanner/candidates/{symbol}`
- `GET /api/v1/scanner/stats`
- `GET /api/v1/scanner/config`
- `POST /api/v1/scanner/run`
- `POST /api/v1/scanner/start`
- `POST /api/v1/scanner/stop`
- `GET /api/v1/opportunities`
- `GET /api/v1/opportunities/top`
- `GET /api/v1/opportunities/{symbol}`
- `GET /api/v1/opportunities/stats`
- `GET /api/v1/opportunities/config`
- `POST /api/v1/opportunities/recalculate`
- `GET /api/v1/setups`
- `GET /api/v1/setups/{symbol}`
- `GET /api/v1/strategies/{symbol}`
- `GET /api/v1/strategies/{symbol}/{strategy}`
- `GET /api/v1/strategies/config`
- `GET /api/v1/strategies/stats`
- `POST /api/v1/strategies/evaluate`
- `GET /api/v1/risk/status`
- `GET /api/v1/risk/config`
- `GET /api/v1/risk/check/{symbol}`
- `GET /api/v1/risk/decisions`
- `POST /api/v1/risk/evaluate`
- `POST /api/v1/risk/recalculate`
- `POST /api/v1/backtests`
- `GET /api/v1/backtests`
- `GET /api/v1/backtests/{backtest_id}`
- `POST /api/v1/backtests/{backtest_id}/run`
- `GET /api/v1/backtests/{backtest_id}/trades`
- `GET /api/v1/backtests/{backtest_id}/equity`
- `GET /api/v1/backtests/{backtest_id}/drawdown`
- `GET /api/v1/backtests/{backtest_id}/report`
- `GET /api/v1/backtests/{backtest_id}/config`

Indicator formulas, UTC/VWAP conventions, structure rules, trend classification, volatility
thresholds, and data-quality behavior are documented in `docs/phase3-analysis.md`.
Phase 4 scanner classifications, pipeline order, state, and control safety are documented in
`docs/phase4-scanner.md`.
Phase 5 factor definitions, directional methodology, hard gates, ranking, and structural-room
estimate are documented in `docs/phase5-scoring.md`.
Phase 6 point-in-time rules, setup definitions, hypothetical level calculations, quality, and
lifecycle behavior are documented in `docs/phase6-strategy-engine.md`.
Phase 7 sizing formulas, loss conventions, configurable guards, state behavior, and execution
boundary are documented in `docs/phase7-risk-engine.md`.
Phase 8 point-in-time access, warmup, execution assumptions, analytics, robustness tools, and
historical-data limitations are documented in `docs/phase8-backtesting.md`.

For backend-only development:

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

## API/documentation assumptions

The implementation uses only endpoints documented in the [official CoinDCX API reference](https://docs.coindcx.com/):

- `GET /exchange/v1/derivatives/futures/data/active_instruments`
- `GET /exchange/v1/derivatives/futures/data/instrument`
- `GET /exchange/v1/derivatives/futures/data/trades`
- `GET https://public.coindcx.com/market_data/candlesticks`
- `GET https://public.coindcx.com/market_data/v3/orderbook/{pair}-futures/{depth}`

REST candle sources are limited to documented resolutions (`5`, `60`, `1D`) for the required frames. The service aggregates 15m from 5m, 4h from 1h, and ISO weeks from daily candles. REST request timestamps are seconds; REST response candle timestamps are milliseconds; WebSocket candle `open_time` is seconds. Conversion functions are deliberately separate.

The official general CoinDCX limit is 16 requests/second. The client defaults to 15 requests/second and retries HTTP 429 using `Retry-After` when supplied. Futures streaming uses the documented Socket.IO endpoint and public channels only. No authentication data is sent over the WebSocket.

## Deliberately deferred

Phase 10 live exchange execution, private authentication, native exchange TP/SL, and
live position modification remain deliberately absent. Phase 9 sends zero real orders.
