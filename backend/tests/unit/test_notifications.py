import pytest
from app.services.notifications.dispatcher import NotificationDispatcher, format_ist


@pytest.mark.asyncio
async def test_notification_dispatcher_format_ist():
    ist_str = format_ist()
    assert "IST" in ist_str
    assert len(ist_str) > 10


@pytest.mark.asyncio
async def test_notification_trade_entry_and_exit_payloads():
    dispatcher = NotificationDispatcher(ntfy_topic="test_topic_123")
    captured = []

    async def mock_broadcast(title, text, priority="high", tags=None, click_url=None):
        captured.append({"title": title, "text": text, "priority": priority, "tags": tags})

    dispatcher.broadcast = mock_broadcast

    # 1. Trade entry
    await dispatcher.notify_trade_entry(
        symbol="DOGEUSDT",
        side="buy",
        quantity=500.0,
        entry_price=0.0985,
        leverage=3,
        target_price=0.1002,
        stop_price=0.0973,
        margin=16.42,
    )
    assert len(captured) == 1
    assert "DOGEUSDT" in captured[0]["title"]
    assert "BUY (LONG) @ 3x Isolated" in captured[0]["text"]
    assert "0.0985" in captured[0]["text"]
    assert "Take Profit" in captured[0]["text"]
    assert "Stop Loss" in captured[0]["text"]

    # 2. Trade exit
    await dispatcher.notify_trade_exit(
        symbol="DOGEUSDT",
        exit_price=0.1002,
        pnl=0.85,
        roe_pct=5.18,
        reason="TAKE_PROFIT_TRIGGER",
        available_balance=1059.92,
    )
    assert len(captured) == 2
    assert "TRADE CLOSED: DOGEUSDT" in captured[1]["title"]
    assert "+$0.85 USDT" in captured[1]["text"]
    assert "+5.18% ROE" in captured[1]["text"]

    # 3. Potential breakout setup
    await dispatcher.notify_potential_setup(
        symbol="XRPUSDT",
        strategy="breakout",
        direction="long",
        score=88.5,
        trigger_price=0.552,
        target_price=0.568,
        stop_price=0.544,
        risk_reward=2.0,
    )
    assert len(captured) == 3
    assert "BREAKOUT DETECTED: XRPUSDT" in captured[2]["title"]
    assert "88/100" in captured[2]["text"]

    # 4. Daily profit target
    await dispatcher.notify_daily_profit_target(today_pnl=10.25, target_ceiling=10.0)
    assert len(captured) == 4
    assert "DAILY PROFIT GOAL REACHED" in captured[3]["title"]
    assert "+$10.25 USDT" in captured[3]["text"]


@pytest.mark.asyncio
async def test_notification_test_alert():
    dispatcher = NotificationDispatcher(ntfy_topic="fno_trades_apurba")
    async def mock_broadcast(*args, **kwargs):
        pass
    dispatcher.broadcast = mock_broadcast
    res = await dispatcher.send_test_alert()
    assert res["status"] in {"success", "dispatched"}
    assert res["ntfy_topic"] == "fno_trades_apurba"
