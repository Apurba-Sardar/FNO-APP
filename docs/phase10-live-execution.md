# Phase 10 live execution boundary

Phase 10 adds a staged CoinDCX USDT futures adapter. It does not enable live trading by default.

## Safety and rollout

- Stage 0: paper only (default).
- Stage 1: authenticated wallet/order/position connectivity and reconciliation only.
- Stage 2: server-side setup and risk validation without submission.
- Stage 3: manual tiny-notional execution after reconciliation, arming, and a 30-second two-step confirmation.
- Stage 4: manual conservative execution.
- Stage 5: optional automatic execution; `LIVE_AUTO_EXECUTION` must also be explicitly enabled.

A process restart always restores `DISABLED`, never `ARMED` or `READY`. A successful exchange reconciliation and explicit operator arming are required. Emergency stop persists and blocks entries without closing positions. Unknown submission results are never retried until reconciliation establishes that a duplicate is impossible.

## Official API conventions used

The implementation follows the [CoinDCX API reference](https://docs.coindcx.com/): compact JSON is signed with HMAC-SHA256, and the exact signed bytes are sent with `X-AUTH-APIKEY` and `X-AUTH-SIGNATURE`. Authenticated timestamps are epoch milliseconds; the documented order freshness window is ten seconds, so the local guard uses nine seconds.

Integrated futures endpoints:

- `GET /exchange/v1/derivatives/futures/wallets`
- `POST /exchange/v1/derivatives/futures/orders`
- `POST /exchange/v1/derivatives/futures/orders/create`
- `POST /exchange/v1/derivatives/futures/orders/cancel`
- `POST /exchange/v1/derivatives/futures/positions`
- `POST /exchange/v1/derivatives/futures/positions/exit`
- `POST /exchange/v1/derivatives/futures/positions/create_tpsl`
- `POST /exchange/v1/derivatives/futures/trades`

Market orders omit `time_in_force`; the builder sends the documented futures pair, server-derived quantity and leverage, `USDT` margin currency, and explicit `position_margin_type`. TP/SL uses `take_profit_market` and `stop_market` and is verified against the exchange position.

## Explicit assumptions and limitations

- CoinDCX documentation labels timestamps as “seconds” in some tables while every current code sample generates milliseconds. This implementation follows the samples and the documented ten-second order-age behavior: epoch milliseconds.
- The wallet response documents total wallet balance as `balance + locked_balance`; that is used as live equity. Available balance is `balance`.
- CoinDCX position state is the authority for actual quantity, fill price, leverage, margin type, and TP/SL trigger state.
- Clock offset injection exists, but the public reference does not document a server-time endpoint. Stage 3+ must run on a host with a monitored, synchronized system clock; a clock marked untrusted blocks signing.
- Leverage mutation is intentionally not implemented. Even if `LIVE_ALLOW_LEVERAGE_CHANGE` is true, a mismatch is rejected until a separately verified official leverage-change workflow is added.
- No real-order test is performed automatically. It requires credentials, Stage 3 configuration, reconciliation, operator arming, the smallest permitted notional, and explicit action-time confirmation.
