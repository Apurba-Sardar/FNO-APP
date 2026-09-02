from types import SimpleNamespace

from app.backtesting.config import SlippageModelKind
from app.backtesting.execution import SlippageModel


def paper_slippage_model(entry_bps: float, exit_bps: float) -> SlippageModel:
    """Reuse Phase 8's adverse fill-direction implementation."""
    return SlippageModel(SimpleNamespace(
        kind=SlippageModelKind.FIXED_BPS,
        entry_slippage_bps=entry_bps,
        exit_slippage_bps=exit_bps,
        volatility_multiplier=1,
    ))
