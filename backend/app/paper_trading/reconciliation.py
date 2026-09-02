from .models import PaperOrderStatus, PaperPositionStatus, PaperState


def reconcile(state: PaperState) -> list[str]:
    """Repair only safe internal inconsistencies; never creates a second position."""
    warnings = []
    position_order_ids = {item.order_id for item in state.positions}
    for order in state.orders:
        if (
            order.status == PaperOrderStatus.FILLED
            and order.order_type == "market"
            and order.order_id not in position_order_ids
        ):
            order.status = PaperOrderStatus.REJECTED
            order.rejection_reason = "recovery: filled order had no position"
            warnings.append(f"orphaned entry order {order.order_id} rejected")
    seen = set()
    for position in state.positions:
        if position.status == PaperPositionStatus.OPEN:
            if position.symbol in seen:
                position.status = PaperPositionStatus.CLOSING
                warnings.append(f"duplicate recovered position for {position.symbol} quarantined")
            seen.add(position.symbol)
    return warnings
