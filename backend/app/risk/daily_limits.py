from datetime import timedelta

from .config import RiskConfig
from .models import AccountSnapshot


def trading_day(evaluation_timestamp, boundary_hour: int):
    shifted = evaluation_timestamp - timedelta(hours=boundary_hour)
    return shifted.date()


def daily_loss(account: AccountSnapshot, config: RiskConfig) -> tuple[float, float, float]:
    # Deposits, withdrawals, and transfers are excluded. Funding is included as P&L.
    pnl = account.realized_pnl_today + account.funding_today - account.fees_today
    if config.include_unrealized_loss_in_daily_limit and account.unrealized_pnl < 0:
        pnl += account.unrealized_pnl
    loss = max(0.0, -pnl)
    basis = account.starting_day_equity or account.account_equity
    percent = loss / basis * 100 if basis and basis > 0 else 0.0
    return pnl, loss, percent

