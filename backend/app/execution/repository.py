from uuid import UUID

from sqlalchemy import select

from app.db.models import (
    LiveAuditRecord,
    LiveExecutionRequestRecord,
    LiveOrderRecord,
    LivePositionRecord,
    LiveRuntimeRecord,
)

from .models import AuditEvent, ExecutionIntent, LiveOrder, LivePosition


class LiveExecutionRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def load(self):
        async with self.session_factory() as session:
            intents = (await session.scalars(select(LiveExecutionRequestRecord))).all()
            orders = (await session.scalars(select(LiveOrderRecord))).all()
            positions = (await session.scalars(select(LivePositionRecord))).all()
            runtime = await session.get(LiveRuntimeRecord, "current")
        return (
            [ExecutionIntent.model_validate(item.payload) for item in intents],
            [LiveOrder.model_validate(item.payload) for item in orders],
            [LivePosition.model_validate(item.payload) for item in positions],
            {} if runtime is None else runtime.payload,
        )

    async def save_intent(self, intent: ExecutionIntent) -> None:
        async with self.session_factory() as session, session.begin():
            record = await session.get(LiveExecutionRequestRecord, intent.execution_request_id)
            payload = intent.model_dump(mode="json")
            if record is None:
                session.add(LiveExecutionRequestRecord(
                    execution_request_id=intent.execution_request_id,
                    setup_id=intent.setup_id,
                    status=intent.state.value,
                    payload=payload,
                ))
            else:
                record.status = intent.state.value
                record.payload = payload

    async def save_order(self, order: LiveOrder) -> None:
        async with self.session_factory() as session, session.begin():
            record = await session.get(LiveOrderRecord, order.order_id)
            payload = order.model_dump(mode="json")
            if record is None:
                session.add(LiveOrderRecord(
                    order_id=order.order_id,
                    execution_request_id=order.execution_request_id,
                    exchange_order_id=order.exchange_order_id,
                    status=order.status.value,
                    payload=payload,
                ))
            else:
                record.exchange_order_id = order.exchange_order_id
                record.status = order.status.value
                record.payload = payload

    async def save_position(self, position: LivePosition) -> None:
        async with self.session_factory() as session, session.begin():
            record = (await session.scalars(select(LivePositionRecord).where(LivePositionRecord.exchange_position_id == position.exchange_position_id))).first()
            if record is None:
                record = await session.get(LivePositionRecord, position.position_id)
            payload = position.model_dump(mode="json")
            if record is None:
                session.add(LivePositionRecord(
                    position_id=position.position_id,
                    exchange_position_id=position.exchange_position_id,
                    pair=position.pair,
                    status=position.status,
                    protection_status=position.protection_status.value,
                    payload=payload,
                ))
            else:
                record.status = position.status
                record.protection_status = position.protection_status.value
                record.payload = payload

    async def save_runtime(self, payload: dict) -> None:
        async with self.session_factory() as session, session.begin():
            record = await session.get(LiveRuntimeRecord, "current")
            if record is None:
                session.add(LiveRuntimeRecord(key="current", payload=payload))
            else:
                record.payload = payload

    async def append_audit(self, event: AuditEvent) -> None:
        async with self.session_factory() as session, session.begin():
            session.add(LiveAuditRecord(
                event_id=event.event_id,
                timestamp=event.timestamp,
                event_type=event.event_type,
                execution_request_id=event.execution_request_id,
                payload=event.model_dump(mode="json"),
            ))


class InMemoryLiveRepository:
    def __init__(self):
        self.intents: dict[UUID, ExecutionIntent] = {}
        self.orders: dict[UUID, LiveOrder] = {}
        self.positions: dict[UUID, LivePosition] = {}
        self.audits: list[AuditEvent] = []
        self.runtime: dict = {}

    async def load(self):
        return list(self.intents.values()), list(self.orders.values()), list(self.positions.values()), self.runtime

    async def save_intent(self, intent): self.intents[intent.execution_request_id] = intent
    async def save_order(self, order): self.orders[order.order_id] = order
    async def save_position(self, position): self.positions[position.position_id] = position
    async def save_runtime(self, payload): self.runtime = payload
    async def append_audit(self, event): self.audits.append(event)
