from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.market_data.models import Market

from .config import RiskConfig
from .fees import FeeEstimator
from .slippage import SlippageEstimator


@dataclass(frozen=True)
class PositionSize:
    quantity: float
    notional: float
    stop_risk: float
    fees: float
    slippage: float
    maximum_loss: float


def quantity_step(instrument: Market | None) -> float | None:
    if instrument is None:
        return None
    if instrument.step_size and instrument.step_size > 0:
        return instrument.step_size
    if instrument.quantity_precision is not None and instrument.quantity_precision >= 0:
        return 10 ** (-instrument.quantity_precision)
    return None


def round_quantity_down(quantity: float, step: float) -> float:
    if quantity <= 0 or step <= 0:
        return 0.0
    value = Decimal(str(quantity))
    increment = Decimal(str(step))
    return float((value / increment).to_integral_value(rounding=ROUND_DOWN) * increment)


class PositionSizer:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self.fees = FeeEstimator(config)
        self.slippage = SlippageEstimator(config)

    def calculate(
        self,
        *,
        entry: float,
        stop: float,
        risk_budget: float,
        effective_slippage_percent: float,
        instrument: Market,
        maximum_new_notional: float,
    ) -> PositionSize:
        stop_per_unit = abs(entry - stop)
        fee_per_unit = self.fees.maximum_loss_fees(1, entry, stop)
        slippage_per_unit = self.slippage.cost(1, entry, effective_slippage_percent)
        loss_per_unit = stop_per_unit + fee_per_unit + slippage_per_unit
        raw = risk_budget / loss_per_unit if loss_per_unit > 0 else 0
        raw = min(
            raw,
            self.config.max_position_notional / entry,
            max(0, maximum_new_notional) / entry,
        )
        step = quantity_step(instrument)
        quantity = round_quantity_down(raw, step) if step else 0
        notional = entry * quantity
        stop_risk = stop_per_unit * quantity
        fees = self.fees.maximum_loss_fees(quantity, entry, stop)
        slippage = self.slippage.cost(quantity, entry, effective_slippage_percent)
        return PositionSize(
            quantity=quantity,
            notional=notional,
            stop_risk=stop_risk,
            fees=fees,
            slippage=slippage,
            maximum_loss=stop_risk + fees + slippage,
        )

