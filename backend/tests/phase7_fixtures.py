from datetime import UTC, datetime, timedelta

from app.market_data.models import Market, MarketType
from app.risk.config import RiskConfig
from app.risk.engine import RiskEngine
from app.risk.models import AccountSnapshot, RiskContext
from app.strategy.models import (
    EntryMethod,
    SetupQuality,
    StopMethod,
    StrategyDirection,
    StrategyName,
    StrategyResult,
    StrategyStatus,
)

NOW = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)


def instrument(**updates):
    values = {
        "symbol": "B-TEST_USDT",
        "base_asset": "TEST",
        "quote_asset": "USDT",
        "market_type": MarketType.FUTURES,
        "status": "active",
        "quantity_precision": 3,
        "min_quantity": 0.001,
        "min_notional": 5,
        "tick_size": 0.01,
        "step_size": 0.001,
    }
    values.update(updates)
    return Market(**values)


def setup(direction=StrategyDirection.LONG, **updates):
    long = direction == StrategyDirection.LONG
    values = {
        "symbol": "B-TEST_USDT",
        "strategy": StrategyName.TREND_PULLBACK,
        "status": StrategyStatus.TRIGGERED,
        "direction": direction,
        "evaluation_timestamp": NOW,
        "opportunity_score": 80,
        "setup_quality_score": 80,
        "quality": SetupQuality.GOOD,
        "entry_method": EntryMethod.CLOSED_CANDLE_CONFIRMATION,
        "hypothetical_entry": 100,
        "stop_method": StopMethod.STRUCTURE_ATR_BUFFER,
        "hypothetical_stop": 99 if long else 101,
        "hypothetical_target": 102 if long else 98,
        "risk_reward": 2,
        "invalidation_price": 99 if long else 101,
        "expires_at": NOW + timedelta(minutes=60),
    }
    values.update(updates)
    return StrategyResult(**values)


def account(**updates):
    values = {
        "account_equity": 100_000,
        "available_balance": 100_000,
        "starting_day_equity": 100_000,
        "timestamp": NOW,
    }
    values.update(updates)
    return AccountSnapshot(**values)


def context(direction=StrategyDirection.LONG, **updates):
    values = {
        "evaluation_timestamp": NOW,
        "account": account(),
        "strategy_setup": setup(direction),
        "instrument": instrument(),
        "current_price": 100.05,
        "atr": 1,
        "spread_percent": 0.02,
        "estimated_slippage_percent": 0.05,
        "market_data_timestamp": NOW - timedelta(seconds=30),
        "liquidity_usable": True,
    }
    values.update(updates)
    return RiskContext(**values)


def decision(config=None, direction=StrategyDirection.LONG, **updates):
    return RiskEngine(config or RiskConfig()).evaluate(context(direction, **updates))
