import asyncio
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.execution.models import LivePosition, ProtectionStatus
from app.execution.runtime import LiveExecutionRuntime
from app.execution.config import LiveExecutionConfig
from app.execution.repository import InMemoryLiveRepository
from app.strategy.models import StrategyDirection
from app.ai.claude_advisor import ClaudeScalpAdvisor


@pytest.mark.asyncio
async def test_live_position_defaults_to_manual_and_unmanaged():
    pos = LivePosition(
        exchange_position_id="pos_123",
        pair="B-BTC_USDT",
        direction=StrategyDirection.LONG,
        quantity=0.1,
        average_price=60000.0,
        leverage=3,
        margin_mode="isolated",
        margin=2000.0,
    )
    assert pos.bot_managed is False
    assert pos.origin == "manual"
    assert pos.breakeven_activated is False


@pytest.mark.asyncio
async def test_auto_close_skips_manual_trades_even_in_loss():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    repo = InMemoryLiveRepository()
    mock_client = MagicMock()
    mock_client.exit_position = AsyncMock()

    runtime = LiveExecutionRuntime(config, repo, client=mock_client)
    
    # Manual position with large unrealized loss
    manual_pos = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_manual_1",
        pair="B-XRP_USDT",
        direction=StrategyDirection.LONG,
        quantity=100.0,
        average_price=2.00,
        mark_price=1.00,  # 50% loss!
        unrealized_pnl=-100.0,
        margin=66.6,
        leverage=3,
        margin_mode="isolated",
        bot_managed=False,  # User manual trade!
        origin="manual",
        status="open",
    )
    runtime.positions[manual_pos.position_id] = manual_pos

    actions = await runtime.monitor_and_auto_close_positions()
    
    # Must NOT have taken any action on manual position!
    assert len(actions) == 0
    mock_client.exit_position.assert_not_called()
    assert runtime.positions[manual_pos.position_id].status == "open"


@pytest.mark.asyncio
async def test_auto_close_exits_bot_managed_position_on_target_or_stop():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    repo = InMemoryLiveRepository()
    mock_client = MagicMock()
    mock_client.exit_position = AsyncMock(return_value={"status": "success"})

    runtime = LiveExecutionRuntime(config, repo, client=mock_client)
    
    # Bot-managed scalp position touching profit target
    bot_pos = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_bot_1",
        pair="B-DOGE_USDT",
        direction=StrategyDirection.LONG,
        quantity=500.0,
        average_price=0.100,
        mark_price=0.1015,  # +1.5% profit
        target=0.1011,      # Target at +1.1%
        stop=0.0991,        # Stop at -0.9%
        unrealized_pnl=0.75,
        margin=16.6,
        leverage=3,
        margin_mode="isolated",
        bot_managed=True,   # Bot-managed scalp!
        origin="bot",
        status="open",
    )
    runtime.positions[bot_pos.position_id] = bot_pos

    actions = await runtime.monitor_and_auto_close_positions()
    
    assert len(actions) == 1
    assert "TAKE_PROFIT_TRIGGER" in actions[0]["reason"]
    mock_client.exit_position.assert_called_once_with("pos_bot_1")


@pytest.mark.asyncio
async def test_claude_advisor_algorithmic_fallback():
    advisor = ClaudeScalpAdvisor(api_key="")  # No key configured
    assert advisor.is_configured is False

    analysis = await advisor.analyze_scalp(
        symbol="B-SOL_USDT",
        current_price=150.0,
        direction="buy",
        metrics={"score": 85, "rsi": 55.0},
    )

    assert analysis.symbol == "B-SOL_USDT"
    assert analysis.conviction_score >= 80
    assert analysis.direction == "buy"
    assert "Bullish Flow" in analysis.pro_trader_rationale
    assert analysis.target_price > 150.0
    assert analysis.stop_price < 150.0


@pytest.mark.asyncio
async def test_auto_close_anti_churn_and_daily_win_tracking():
    config = LiveExecutionConfig(trading_mode="live", enabled=True, confirmation="test")
    repo = InMemoryLiveRepository()
    mock_client = MagicMock()
    mock_client.exit_position = AsyncMock(return_value={"status": "success"})
    mock_client.positions = AsyncMock(return_value=[])
    mock_client.orders = AsyncMock(return_value=[])

    runtime = LiveExecutionRuntime(config, repo, client=mock_client)
    runtime.today_winning_trades = 19  # 19 wins already banked today
    
    bot_pos = LivePosition(
        position_id=uuid4(),
        exchange_position_id="pos_win_20",
        pair="B-FORM_USDT",
        direction=StrategyDirection.LONG,
        quantity=300.0,
        average_price=0.33,
        mark_price=0.34,
        target=0.3345,
        stop=0.3247,
        unrealized_pnl=1.20,  # >= +1.15 USDT target!
        margin=25.0,
        leverage=4,
        margin_mode="isolated",
        bot_managed=True,
        origin="bot",
        status="open",
    )
    runtime.positions[bot_pos.position_id] = bot_pos

    actions = await runtime.monitor_and_auto_close_positions()

    assert len(actions) == 1
    assert "PROFIT_TARGET_REACHED" in actions[0]["reason"]
    # Cooldown verification: B-FORM_USDT must be locked
    assert "B-FORM_USDT" in runtime.symbol_cooldowns
    assert runtime.symbol_cooldowns["B-FORM_USDT"] > datetime.now(UTC)
    assert runtime.last_trade_closed_at is not None
    # 20th win banked!
    assert runtime.today_winning_trades == 20
    # Auto-trading should now be paused to protect daily goal
    assert runtime.auto_trading_enabled is False

