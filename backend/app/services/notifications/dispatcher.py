import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
import httpx
import structlog


def format_ist(dt: datetime | None = None) -> str:
    """Convert UTC datetime or current time to Indian Standard Time (IST) string."""
    base = dt or datetime.now(UTC)
    ist = base + timedelta(hours=5, minutes=30)
    return ist.strftime("%d %b %Y, %I:%M:%S %p IST")


class NotificationDispatcher:
    """Dispatches high-priority push notifications to mobile devices (e.g. Samsung Galaxy S24 Ultra).

    Supports:
    1. ntfy.sh (direct instant mobile push via free ntfy Android app from Google Play Store)
    2. Telegram Bot API (direct messages to Telegram chat)
    """

    def __init__(
        self,
        ntfy_topic: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
    ):
        if ntfy_topic is None or telegram_bot_token is None or telegram_chat_id is None:
            try:
                from app.config import get_settings
                settings = get_settings()
                ntfy_topic = ntfy_topic if ntfy_topic is not None else settings.ntfy_topic
                telegram_bot_token = telegram_bot_token if telegram_bot_token is not None else settings.telegram_bot_token
                telegram_chat_id = telegram_chat_id if telegram_chat_id is not None else settings.telegram_chat_id
            except Exception:
                ntfy_topic = ntfy_topic or "fno_trades_apurba"
                telegram_bot_token = telegram_bot_token or ""
                telegram_chat_id = telegram_chat_id or ""

        self.ntfy_topic = (ntfy_topic or "fno_trades_apurba").strip()
        self.telegram_bot_token = (telegram_bot_token or "").strip()
        self.telegram_chat_id = (telegram_chat_id or "").strip()
        self._sent_setups_cooldown: dict[str, float] = {}

    def update_config(
        self,
        ntfy_topic: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
    ) -> None:
        if ntfy_topic is not None:
            self.ntfy_topic = ntfy_topic.strip()
        if telegram_bot_token is not None:
            self.telegram_bot_token = telegram_bot_token.strip()
        if telegram_chat_id is not None:
            self.telegram_chat_id = telegram_chat_id.strip()

    async def _send_ntfy(
        self,
        title: str,
        message: str,
        *,
        priority: str = "high",
        tags: list[str] | None = None,
        click_url: str | None = None,
    ) -> bool:
        if not self.ntfy_topic:
            return False
        url = f"https://ntfy.sh/{self.ntfy_topic}"
        headers = {
            "Title": title,
            "Priority": priority,
        }
        if tags:
            headers["Tags"] = ",".join(tags)
        if click_url:
            headers["Click"] = click_url

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, content=message.encode("utf-8"), headers=headers)
                return res.is_success
        except Exception as exc:
            structlog.get_logger().warning("NTFY_PUSH_FAILED", error=str(exc))
            return False

    async def _send_telegram(self, message: str) -> bool:
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                return res.is_success
        except Exception as exc:
            structlog.get_logger().warning("TELEGRAM_NOTIFICATION_FAILED", error=str(exc))
            return False

    async def broadcast(
        self,
        title: str,
        text_content: str,
        *,
        priority: str = "high",
        tags: list[str] | None = None,
        click_url: str = "http://20.244.21.190:3000/live",
    ) -> None:
        """Send notification across all configured mobile channels."""
        asyncio.create_task(self._send_ntfy(title, text_content, priority=priority, tags=tags, click_url=click_url))
        tg_text = f"<b>{title}</b>\n\n{text_content}"
        asyncio.create_task(self._send_telegram(tg_text))

    async def notify_trade_entry(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int = 3,
        target_price: float | None = None,
        stop_price: float | None = None,
        margin: float | None = None,
    ) -> None:
        """Triggered immediately when a trade entry is punched."""
        is_buy = side.lower() == "buy"
        direction_label = "BUY (LONG)" if is_buy else "SELL (SHORT)"
        title = f"🚀 TRADE PUNCHED: {symbol}"
        lines = [
            f"• Action: {direction_label} @ {leverage}x Isolated",
            f"• Entry Price: ${entry_price:,.6g} USDT",
            f"• Quantity: {quantity:,.4g}",
        ]
        if margin:
            lines.append(f"• Margin Used: ${margin:,.2f} USDT")
        if target_price:
            diff_pct = ((target_price - entry_price) / entry_price * 100) if is_buy else ((entry_price - target_price) / entry_price * 100)
            lines.append(f"• Take Profit (TP): ${target_price:,.6g} (+{diff_pct:.2f}%)")
        if stop_price:
            diff_pct = ((entry_price - stop_price) / entry_price * 100) if is_buy else ((stop_price - entry_price) / entry_price * 100)
            lines.append(f"• Stop Loss (SL): ${stop_price:,.6g} (-{diff_pct:.2f}%)")
        lines.append(f"• Time: {format_ist()}")

        message = "\n".join(lines)
        await self.broadcast(
            title,
            message,
            priority="urgent",
            tags=["rocket", "chart_with_upwards_trend" if is_buy else "chart_with_downwards_trend"],
        )

    async def notify_trade_exit(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        roe_pct: float | None = None,
        reason: str = "TAKE_PROFIT_TRIGGER",
        available_balance: float | None = None,
    ) -> None:
        """Triggered when an open position auto-closes at profit or hits stop."""
        is_profit = pnl >= 0
        icon = "🎯" if is_profit else "🛡️"
        status_label = "TAKE PROFIT HIT (+)" if is_profit else "STOP LOSS HIT (-)"
        title = f"{icon} TRADE CLOSED: {symbol} ({status_label})"

        lines = [
            f"• Result: {'+' if is_profit else ''}${pnl:,.2f} USDT" + (f" ({roe_pct:+.2f}% ROE)" if roe_pct is not None else ""),
            f"• Exit Price: ${exit_price:,.6g} USDT",
            f"• Trigger Reason: {reason}",
        ]
        if available_balance is not None:
            lines.append(f"• Free Cash Balance: ${available_balance:,.2f} USDT")
        lines.append(f"• Time: {format_ist()}")

        message = "\n".join(lines)
        await self.broadcast(
            title,
            message,
            priority="urgent",
            tags=["dart" if is_profit else "shield", "moneybag" if is_profit else "warning"],
        )

    async def notify_potential_setup(
        self,
        symbol: str,
        strategy: str,
        direction: str,
        score: float,
        trigger_price: float | None = None,
        target_price: float | None = None,
        stop_price: float | None = None,
        risk_reward: float | None = None,
    ) -> None:
        """Triggered when a high-probability Tier-A setup is identified."""
        import time
        now_ts = time.time()
        # Cooldown: Don't send same symbol alert more than once every 15 minutes
        last_sent = self._sent_setups_cooldown.get(symbol, 0)
        if now_ts - last_sent < 900:
            return
        self._sent_setups_cooldown[symbol] = now_ts

        title = f"⚡ POTENTIAL BREAKOUT DETECTED: {symbol}"
        lines = [
            f"• Strategy: {strategy.upper()} ({direction.upper()})",
            f"• Opportunity Score: {score:.0f}/100 (Tier A)",
        ]
        if trigger_price:
            lines.append(f"• Trigger Price: ${trigger_price:,.6g} USDT")
        if target_price:
            lines.append(f"• Potential Target: ${target_price:,.6g} USDT")
        if stop_price:
            lines.append(f"• Invalidation Stop: ${stop_price:,.6g} USDT")
        if risk_reward:
            lines.append(f"• Risk:Reward Ratio: 1:{risk_reward:.2f}")
        lines.append(f"• Time: {format_ist()}")

        message = "\n".join(lines)
        await self.broadcast(
            title,
            message,
            priority="high",
            tags=["zap", "mag_right"],
        )

    async def notify_daily_profit_target(
        self,
        today_pnl: float,
        target_ceiling: float = 10.0,
    ) -> None:
        """Triggered when the $10 daily profit target is locked."""
        title = f"🏆 DAILY PROFIT GOAL REACHED (${target_ceiling:.2f} USDT)"
        lines = [
            f"• Cumulative Net Profit Today: +${today_pnl:,.2f} USDT",
            f"• Target Ceiling: ${target_ceiling:,.2f} USDT",
            "• Action: New trade purchases LOCKED for today to secure earnings.",
            f"• Time: {format_ist()}",
        ]
        message = "\n".join(lines)
        await self.broadcast(
            title,
            message,
            priority="urgent",
            tags=["trophy", "star2", "lock"],
        )

    async def send_test_alert(self) -> dict[str, Any]:
        """Send a test notification to verify S24 Ultra connectivity."""
        title = "🔔 S24 Ultra Alert Test — FNO Trading Bot"
        lines = [
            "✅ Mobile Push Notifications are Working!",
            "• Device: Samsung Galaxy S24 Ultra Connected",
            "• Alert Channels: Active",
            "• Automated Trades, Exits & Breakout Setups will ring your phone 24/7.",
            f"• Test Sent: {format_ist()}",
        ]
        message = "\n".join(lines)
        await self.broadcast(
            title,
            message,
            priority="high",
            tags=["bell", "white_check_mark", "iphone"],
        )
        return {
            "status": "dispatched",
            "ntfy_topic": self.ntfy_topic,
            "telegram_configured": bool(self.telegram_bot_token and self.telegram_chat_id),
            "timestamp": format_ist(),
        }


# Global singleton instance
notification_service = NotificationDispatcher()
