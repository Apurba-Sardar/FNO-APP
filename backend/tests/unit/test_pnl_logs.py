import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.strategy.models import StrategyDirection
from app.execution.config import LiveExecutionConfig
from app.execution.models import LivePosition
from app.execution.runtime import LiveExecutionRuntime
from app.execution.repository import InMemoryLiveRepository


@pytest.mark.asyncio
async def test_rehydrate_today_metrics_from_database():
    repo = InMemoryLiveRepository()
    now_t = datetime.now(UTC)
    yesterday_t = now_t - timedelta(days=1)

    # 2 wins today, 1 loss today, 1 win yesterday
    pos_today_win1 = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_today_1",
        pair="B-XRP_USDT",
        direction=StrategyDirection.LONG,
        quantity=100.0,
        average_price=1.5,
        exit_price=1.52,
        realized_pnl=1.25,
        status="closed",
        closed_at=now_t,
        updated_at=now_t,
    )
    pos_today_win2 = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_today_2",
        pair="B-DOGE_USDT",
        direction=StrategyDirection.LONG,
        quantity=500.0,
        average_price=0.25,
        exit_price=0.253,
        realized_pnl=1.10,
        status="closed",
        closed_at=now_t,
        updated_at=now_t,
    )
    pos_today_loss = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_today_3",
        pair="B-SOL_USDT",
        direction=StrategyDirection.SHORT,
        quantity=1.0,
        average_price=180.0,
        exit_price=181.2,
        realized_pnl=-0.65,
        status="closed",
        closed_at=now_t,
        updated_at=now_t,
    )
    pos_yesterday = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_yesterday_1",
        pair="B-ETH_USDT",
        direction=StrategyDirection.LONG,
        quantity=0.1,
        average_price=2500.0,
        exit_price=2530.0,
        realized_pnl=2.50,
        status="closed",
        closed_at=yesterday_t,
        updated_at=yesterday_t,
    )

    await repo.save_position(pos_today_win1)
    await repo.save_position(pos_today_win2)
    await repo.save_position(pos_today_loss)
    await repo.save_position(pos_yesterday)

    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    runtime = LiveExecutionRuntime(config, repo)

    await runtime.load()

    # Verify today's metrics are restored from closed trades
    assert runtime.today_winning_trades == 2
    assert runtime.today_losing_trades == 1
    assert runtime.today_realized_profit == 2.35  # 1.25 + 1.10
    assert runtime.today_realized_loss == 0.65
    net_today = round(runtime.today_realized_profit - runtime.today_realized_loss, 3)
    assert net_today == 1.70


@pytest.mark.asyncio
async def test_refresh_account_preserves_daily_pnl():
    repo = InMemoryLiveRepository()
    mock_client = MagicMock()
    mock_client.wallets = AsyncMock(return_value=[
        {"currency_short_name": "USDT", "balance": "95.50", "locked_balance": "0.0"}
    ])

    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    runtime = LiveExecutionRuntime(config, repo, client=mock_client)
    runtime.today_realized_profit = 3.45
    runtime.today_realized_loss = 0.65
    runtime.today_winning_trades = 3
    runtime.today_losing_trades = 1

    account = await runtime.refresh_account()

    assert account.daily_pnl == 2.80  # 3.45 - 0.65
    assert account.daily_profit == 3.45
    assert account.daily_loss == 0.65
    assert account.daily_wins == 3
    assert account.daily_losses == 1
    assert account.available_balance == 95.50


def test_max_daily_profit_target_default_is_20():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    assert config.max_daily_profit_target == 20.0


@pytest.mark.asyncio
async def test_stale_position_without_closed_at_not_counted_today():
    repo = InMemoryLiveRepository()
    # A position closed in the past without closed_at timestamp
    stale_pos = LivePosition(
        position_id=uuid4(),
        exchange_position_id="P-STALE",
        pair="B-BTC_USDT",
        direction=StrategyDirection.LONG,
        quantity=1.0,
        average_price=50000.0,
        realized_pnl=-0.223,
        status="closed",
        closed_at=None,
        created_at=datetime(2026, 9, 7, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC),  # Updated today due to container restart
    )
    repo.positions = {stale_pos.position_id: stale_pos}

    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    runtime = LiveExecutionRuntime(config, repo)
    await runtime.load()

    # The stale trade with no closed_at must NOT be counted as today's loss!
    assert runtime.today_realized_loss == 0.0
    assert runtime.today_realized_profit == 0.0
    assert runtime.today_losing_trades == 0
    assert runtime.today_winning_trades == 0

