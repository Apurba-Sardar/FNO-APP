from types import SimpleNamespace

from app.backtesting.execution import FeeModel


def paper_fee_model(taker_fee_percent: float) -> FeeModel:
    """Reuse Phase 8's fee formula with the configured Phase 7 taker rate."""
    return FeeModel(SimpleNamespace(
        taker_fee_percent=taker_fee_percent,
        maker_fee_percent=taker_fee_percent,
        use_taker=True,
    ))
