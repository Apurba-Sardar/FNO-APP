from app.strategy.models import StrategyDirection

from .exceptions import ProtectionFailure
from .models import LivePosition, ProtectionStatus


class TPSLManager:
    def __init__(self, client, repository):
        self.client = client
        self.repository = repository

    @staticmethod
    def validate(direction: StrategyDirection, entry: float, stop: float, target: float) -> None:
        valid = (
            stop < entry < target
            if direction == StrategyDirection.LONG
            else target < entry < stop
            if direction == StrategyDirection.SHORT
            else False
        )
        if not valid:
            raise ProtectionFailure("TP/SL is on the wrong side of the actual fill")

    async def protect(self, position: LivePosition, stop: float, target: float) -> LivePosition:
        self.validate(position.direction, position.average_price, stop, target)
        try:
            response = await self.client.create_tpsl(
                position.exchange_position_id, format(stop, ".15g"), format(target, ".15g")
            )
        except Exception as exc:
            failed = position.model_copy(update={"protection_status": ProtectionStatus.FAILED})
            await self.repository.save_position(failed)
            raise ProtectionFailure("native TP/SL request failed") from exc
        parts = [response.get("stop_loss"), response.get("take_profit")] if isinstance(response, dict) else []
        if len(parts) != 2 or any(
            not isinstance(item, dict) or item.get("success") is not True for item in parts
        ):
            failed = position.model_copy(update={"protection_status": ProtectionStatus.FAILED})
            await self.repository.save_position(failed)
            raise ProtectionFailure("CoinDCX did not confirm both native TP and SL requests")
        try:
            rows = await self.client.positions(position_ids=position.exchange_position_id)
        except Exception as exc:
            failed = position.model_copy(update={"protection_status": ProtectionStatus.FAILED})
            await self.repository.save_position(failed)
            raise ProtectionFailure("native TP/SL verification failed") from exc
        match = next((row for row in rows if str(row.get("id")) == position.exchange_position_id), None)
        price_tolerance = max(abs(position.average_price) * 1e-10, 1e-12)
        verified = bool(
            match
            and abs(float(match.get("stop_loss_trigger") or 0) - stop) <= price_tolerance
            and abs(float(match.get("take_profit_trigger") or 0) - target) <= price_tolerance
        )
        updated = position.model_copy(update={
            "stop": stop,
            "target": target,
            "protection_status": ProtectionStatus.PROTECTED if verified else ProtectionStatus.UNPROTECTED,
        })
        await self.repository.save_position(updated)
        if not verified:
            raise ProtectionFailure("native TP/SL could not be verified from exchange position state")
        return updated
