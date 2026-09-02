from datetime import UTC, datetime

from app.risk.models import AccountSnapshot, OpenPosition

from .models import PaperPositionStatus, PaperState


def refresh_account(state: PaperState, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if state.account.trading_day != now.date():
        state.account.trading_day = now.date()
        state.account.starting_day_equity = state.account.equity
        state.account.daily_pnl = 0
    open_positions = [item for item in state.positions if item.status == PaperPositionStatus.OPEN]
    state.account.unrealized_pnl = sum(item.unrealized_pnl for item in open_positions)
    state.account.margin_used = sum(item.notional / max(item.leverage, 1) for item in open_positions)
    state.account.total_exposure = sum(item.notional for item in open_positions)
    # Closed net P&L already includes both fees. Entry fees on open positions are
    # charged immediately and are therefore deducted exactly once here.
    open_entry_fees = sum(item.entry_fee for item in open_positions)
    state.account.equity = max(
        0.00000001,
        state.account.initial_equity
        + state.account.realized_pnl
        + state.account.unrealized_pnl
        - open_entry_fees,
    )
    state.account.available_balance = max(
        0, state.account.equity - state.account.margin_used
    )
    state.account.peak_equity = max(state.account.peak_equity, state.account.equity)
    state.account.drawdown = state.account.peak_equity - state.account.equity
    state.account.updated_at = now


def account_snapshot(state: PaperState, now: datetime) -> AccountSnapshot:
    account = state.account
    return AccountSnapshot(
        account_equity=account.equity,
        available_balance=account.available_balance,
        starting_day_equity=account.starting_day_equity or account.equity,
        realized_pnl_today=account.daily_pnl,
        unrealized_pnl=account.unrealized_pnl,
        fees_today=account.fees,
        funding_today=-account.funding_cost,
        consecutive_losses=account.consecutive_losses,
        open_positions=[
            OpenPosition(
                symbol=item.symbol,
                direction=item.direction,
                notional=item.notional,
                status="confirmed_open",
            )
            for item in state.positions
            if item.status == PaperPositionStatus.OPEN
        ],
        timestamp=now,
    )
