from app.risk.config import RiskConfig
from app.risk.models import RiskLockState
from app.risk.state import RiskStateStore
from tests.phase7_fixtures import NOW, account


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}

    async def get(self, key):
        return self.values.get(key)

    async def hgetall(self, key):
        return self.hashes.get(key, {})

    def pipeline(self, transaction=True):
        return MemoryPipeline(self)


class MemoryPipeline:
    def __init__(self, redis):
        self.redis = redis

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def set(self, key, value):
        self.redis.values[key] = value

    def delete(self, key):
        self.redis.hashes.pop(key, None)

    def hset(self, key, mapping):
        self.redis.hashes[key] = mapping

    async def execute(self):
        return []


async def test_risk_state_and_lock_survive_restart():
    redis = MemoryRedis()
    config = RiskConfig()
    original = RiskStateStore(redis, config)
    original.update_account(account(consecutive_losses=3), NOW)
    assert original.risk_state.trading_lock == RiskLockState.BLOCKED
    await original.persist()
    restored = RiskStateStore(redis, config)
    await restored.load()
    assert restored.risk_state.account.consecutive_losses == 3
    assert restored.risk_state.trading_lock == RiskLockState.BLOCKED


def test_healthy_account_opens_lock_and_daily_loss_resets_only_on_new_day():
    state = RiskStateStore(None, RiskConfig())
    state.update_account(account(realized_pnl_today=-100), NOW)
    assert state.risk_state.trading_lock == RiskLockState.OPEN
    assert state.risk_state.daily_loss == 100
    state.update_account(account(realized_pnl_today=-100), NOW.replace(day=2))
    assert state.risk_state.daily_loss == 0
    assert state.risk_state.account.consecutive_losses == 0


def test_loaded_account_is_blocked_when_startup_reconciliation_finds_it_stale():
    state = RiskStateStore(None, RiskConfig(max_account_data_age_seconds=300))
    state.update_account(account(), NOW)
    assert state.risk_state.trading_lock == RiskLockState.OPEN
    state.update_account(state.risk_state.account, NOW + timedelta(seconds=301))
    assert state.risk_state.trading_lock == RiskLockState.BLOCKED
    assert "account data unavailable" in state.risk_state.block_reasons
from datetime import timedelta
