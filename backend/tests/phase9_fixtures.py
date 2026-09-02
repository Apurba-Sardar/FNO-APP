from datetime import UTC, datetime

from app.paper_trading.config import PaperTradingConfig
from app.paper_trading.execution import PaperTradeExecutor
from app.paper_trading.models import MarketQuote
from app.paper_trading.state import InMemoryPaperStateRepository
from app.strategy.models import StrategyDirection
from tests.phase7_fixtures import decision, setup

NOW = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)


def quote(symbol="B-TEST_USDT", bid=99.9, ask=100.1, last=100, timestamp=NOW):
    return MarketQuote(symbol=symbol, bid=bid, ask=ask, last=last, timestamp=timestamp)


def harness(config=None):
    config = config or PaperTradingConfig()
    repository = InMemoryPaperStateRepository(config.initial_equity)
    state = repository.new_state()
    executor = PaperTradeExecutor(config, 0.05)
    return config, repository, state, executor


def approved(direction=StrategyDirection.LONG, symbol="B-TEST_USDT"):
    item = decision(direction=direction)
    return item.model_copy(update={"symbol": symbol})


def triggered(direction=StrategyDirection.LONG, symbol="B-TEST_USDT"):
    return setup(direction, symbol=symbol)
