from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.main import create_authenticated_live_client
from app.paper_trading.config import PaperTradingConfig
from app.paper_trading.execution import PaperTradeExecutor
from app.paper_trading.models import MarketQuote
from app.paper_trading.state import InMemoryPaperStateRepository
from app.risk.models import RiskDecision, RiskDecisionStatus
from app.strategy.models import StrategyDirection, StrategyName, StrategyResult, StrategyStatus


def test_paper_mode_never_constructs_authenticated_client_even_when_credentials_exist():
    settings = Settings(
        _env_file=None,
        trading_mode="paper",
        coindcx_api_key="must-not-be-used",
        coindcx_api_secret="must-not-be-used",
    )
    assert create_authenticated_live_client(settings) is None


def test_paper_executor_has_no_private_exchange_transport_and_records_lifecycles():
    now = datetime.now(UTC)
    executor = PaperTradeExecutor(PaperTradingConfig(), 0.05)
    assert executor.mode.value == "paper"
    assert not hasattr(executor, "client")
    state = InMemoryPaperStateRepository().new_state()
    setup = StrategyResult.model_construct(
        symbol="B-BTC_USDT", strategy=StrategyName.TREND_PULLBACK,
        status=StrategyStatus.TRIGGERED, direction=StrategyDirection.LONG,
        evaluation_timestamp=now, expires_at=now + timedelta(minutes=5),
        hypothetical_entry=100, hypothetical_stop=98, hypothetical_target=104,
        opportunity_score=80, setup_quality_score=75,
    )
    decision = RiskDecision.model_construct(
        symbol=setup.symbol, strategy=setup.strategy, direction=setup.direction,
        allowed=True, status=RiskDecisionStatus.APPROVED, evaluation_timestamp=now,
        position_quantity=1, estimated_leverage=1, maximum_loss=2, checks=[],
    )
    position = executor.execute_entry(
        state, setup, decision,
        MarketQuote(symbol=setup.symbol, bid=99.9, ask=100, last=99.95, timestamp=now),
        now, "unique-setup",
    )
    assert state.orders[0].lifecycle == ["intent_created", "validating", "submitting", "filled"]
    assert position.protection_status == "protected"
    assert position.protection_lifecycle[-1] == "protected"
    assert len([item for item in state.orders if item.order_type == "market"]) == 1
