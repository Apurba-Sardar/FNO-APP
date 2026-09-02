# Phase 7 risk engine

Phase 7 is a deterministic, execution-agnostic risk authority. It consumes normalized Phase 4
market state, Phase 6 hypothetical setups, explicit account state, and Phase 2 instrument
constraints. It never queries CoinDCX and cannot place, cancel, or modify an order or position.

## Default policy

- Per-trade all-in loss budget: 0.50% of current account equity.
- Daily loss ceiling: 2.00%; maximum consecutive losses: 3; maximum confirmed-open
  positions: 1.
- Total notional exposure ceiling: 100% of equity; maximum leverage: 5x; maximum position
  notional: 100,000 account-currency units.
- Minimum structural R:R: 1.5; stop distance: 0.4 through 4.0 ATR.
- Maximum spread: 0.25%; maximum effective slippage: 0.35%. Effective slippage is the supplied
  market estimate plus a 0.05% safety buffer. Missing values reject by default.
- Setup age: 60 minutes; account snapshot age: 300 seconds; market snapshot age: 300 seconds;
  entry drift: 0.25%; maximum future trade duration: 240 minutes.
- Default fee assumption: 0.05% taker fee per side. Maker (0.02%) and taker rates are both
  configurable; this is an estimate, not a claim about a universal CoinDCX fee tier.

All values are configured under the `RISK__` environment namespace. Leverage only changes the
margin requirement; it never scales the allowed loss budget.

## Sizing and maximum loss

For a long, stop loss per unit is `entry - stop`; for a short it is `stop - entry`. The raw
quantity solves:

`risk budget / (stop distance + round-trip fees per unit + round-trip slippage per unit)`

Quantity is capped by position-notional and remaining portfolio-exposure limits, then rounded
down to the exchange step/precision. All values are recalculated after rounding. Minimum quantity
and notional constraints are validated without increasing size. An approval requires:

`stop risk + estimated entry/exit fees + estimated round-trip slippage <= risk budget`

Estimated reward is the gross structural target distance times quantity. No profit probability is
produced. Contract multipliers are not inferred: normalized Phase 2 spot-like quantity constraints
are used, and an instrument with no usable quantity step is rejected.

## Daily state and locks

The trading day is a configurable UTC boundary (00:00 UTC by default). Daily P&L includes realized
P&L and funding, subtracts fees, and optionally includes negative unrealized P&L. Deposits,
withdrawals, and transfers are excluded. Positive unrealized P&L is not used to increase the limit.
The Redis risk state and decisions have no TTL, so application restart does not reset daily loss,
consecutive losses, known positions, or the lock. A configured Redis deployment still needs its own
durability policy. Future authenticated account reconciliation remains deliberately deferred.

The lock is blocked for missing/stale account data, a reached daily or consecutive-loss limit, or
the confirmed-open-position ceiling. Each point-in-time decision independently rechecks account,
setup, instrument, market quality, exposure, leverage, margin, and all-in loss constraints.

## API and safety boundary

Read-only/non-executing routes are exposed at `/api/v1/risk/status`, `/api/v1/risk/config`,
`/api/v1/risk/check/{symbol}`, and `/api/v1/risk/decisions`. POST evaluation/recalculation routes
only run calculations and optionally persist normalized account state; they cannot trade. If a
control token is configured, mutations require `x-risk-control-token`.

Liquidation price remains unavailable because normalized account/instrument data is insufficient
for an exchange-accurate estimate. A later execution layer must revalidate this risk decision and
the centralized lock immediately before any order attempt.
