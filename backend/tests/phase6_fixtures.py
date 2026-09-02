from app.indicators import IndicatorEngine
from app.scoring.config import ScoringConfig
from app.scoring.engine import OpportunityScoringEngine
from app.strategy.config import StrategyConfig
from app.strategy.context import StrategyContextBuilder
from app.strategy.engine import StrategyEngine
from tests.phase5_fixtures import candidate


def strategy_fixture(slope: float = 0.2, symbol: str = "B-SETUP_USDT", config=None):
    market = candidate(slope, symbol)
    opportunity = OpportunityScoringEngine(ScoringConfig()).score_candidate(market)
    settings = config or StrategyConfig(minimum_setup_quality=0)
    builder = StrategyContextBuilder(IndicatorEngine(), settings)
    engine = StrategyEngine(builder, settings)
    return market, opportunity, settings, builder, engine
