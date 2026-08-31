# CoinDCX USDT Futures Scalping System

Phase 1 of a deterministic, safety-first futures scanner. Trading decisions are quantitative; no LLM has an execution role. **The default is PAPER and this phase contains no live-order code or UI switch.**

## Included in Phase 1

- Next.js/TypeScript/Tailwind dashboard shell with shadcn-style primitives
- FastAPI backend with typed environment configuration and structured JSON logging
- PostgreSQL models for instruments, candles, scan runs, opportunities, trades, orders, and system events
- Redis/PostgreSQL development services in Docker Compose
- Documented CoinDCX public futures client with bounded retry/backoff
- USDT futures discovery, candles, deterministic timeframe aggregation, and order-book analytics
- One reusable indicator engine: EMA 20/50/200, RSI, MACD, ATR, VWAP, volume average, relative volume, swings, support/resistance
- Multi-timeframe analysis, configurable 0–100 scoring, and hard pre-score market filters
- Unit and mocked integration tests; no real credentials

## Run locally

```bash
copy .env.example .env
docker compose up --build
```

API docs: `http://localhost:8000/docs`; dashboard: `http://localhost:3000`.

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

REST candle sources are limited to documented resolutions (`5`, `60`, `1D`) for the required Phase 1 frames. The service aggregates 15m from 5m, 4h from 1h, and ISO weeks from daily candles. Scanner thresholds and score weights are configuration objects and can later move to persisted strategy profiles.

## Deliberately deferred

Strategies, risk/position sizing, backtesting, paper fills, execution, private authentication, WebSockets, startup reconciliation, native TP/SL, and position monitoring belong to later phases. Their database boundaries are reserved, but placeholder trading behavior is intentionally absent. Tests for those capabilities will be introduced with their implementations.

