from datetime import UTC, datetime

import structlog
from sqlalchemy import delete

from app.db.models import (
    PaperAccountRecord,
    PaperOrderRecord,
    PaperPositionRecord,
    PaperRuntimeRecord,
    PaperSessionRecord,
    PaperSetupRecord,
    PaperTradeRecord,
)

from .models import PaperAccount, PaperState


class PaperStateRepository:
    """Durable snapshot repository. Each save is one PostgreSQL transaction."""

    def __init__(self, session_factory, initial_equity: float) -> None:
        self.session_factory = session_factory
        self.initial_equity = initial_equity

    def new_state(self) -> PaperState:
        now = datetime.now(UTC)
        account = PaperAccount(
            initial_equity=self.initial_equity,
            equity=self.initial_equity,
            available_balance=self.initial_equity,
            peak_equity=self.initial_equity,
            starting_day_equity=self.initial_equity,
            trading_day=now.date(),
            updated_at=now,
        )
        return PaperState(account=account)

    async def load(self) -> PaperState:
        async with self.session_factory() as session:
            row = await session.get(PaperRuntimeRecord, "current")
            if row is None:
                return self.new_state()
            state = PaperState.model_validate(row.payload)
            state.state_recovery_status = "restored"
            structlog.get_logger().info(
                "PAPER_STATE_RESTORED",
                open_positions=sum(item.status.value == "open" for item in state.positions),
                timestamp=datetime.now(UTC).isoformat(),
            )
            return state

    async def save(self, state: PaperState) -> None:
        """Atomically persist order, position, account, journal, setup, and runtime state."""
        async with self.session_factory() as session, session.begin():
            await session.merge(PaperAccountRecord(
                account_id=state.account.account_id,
                payload=state.account.model_dump(mode="json"),
            ))
            for item in state.sessions:
                await session.merge(PaperSessionRecord(
                    session_id=item.session_id,
                    status="active" if item.end_time is None else "completed",
                    payload=item.model_dump(mode="json"),
                ))
            for item in state.orders:
                await session.merge(PaperOrderRecord(
                    order_id=item.order_id,
                    idempotency_key=item.idempotency_key,
                    status=item.status.value,
                    payload=item.model_dump(mode="json"),
                ))
            for item in state.positions:
                await session.merge(PaperPositionRecord(
                    position_id=item.position_id,
                    pair=item.symbol,
                    status=item.status.value,
                    payload=item.model_dump(mode="json"),
                ))
            for item in state.trades:
                await session.merge(PaperTradeRecord(
                    trade_id=item.trade_id,
                    session_id=item.session_id,
                    pair=item.symbol,
                    payload=item.model_dump(mode="json"),
                ))
            for item in state.setups.values():
                await session.merge(PaperSetupRecord(
                    setup_id=item.setup_id,
                    status=item.status.value,
                    payload=item.model_dump(mode="json"),
                ))
            await session.merge(PaperRuntimeRecord(
                key="current", payload=state.model_dump(mode="json")
            ))

    async def reset(self, state: PaperState) -> None:
        """Clear current paper lifecycle data while preserving historical sessions."""
        historical = list(state.sessions)
        async with self.session_factory() as session, session.begin():
            for table in (
                PaperAccountRecord,
                PaperOrderRecord,
                PaperPositionRecord,
                PaperTradeRecord,
                PaperSetupRecord,
            ):
                await session.execute(delete(table))
            fresh = self.new_state()
            fresh.sessions = historical
            await session.merge(PaperAccountRecord(
                account_id=fresh.account.account_id,
                payload=fresh.account.model_dump(mode="json"),
            ))
            await session.merge(PaperRuntimeRecord(key="current", payload=fresh.model_dump(mode="json")))


class InMemoryPaperStateRepository(PaperStateRepository):
    """Deterministic test repository with the same snapshot semantics."""

    def __init__(self, initial_equity: float = 100_000) -> None:
        self.initial_equity = initial_equity
        self.persisted: PaperState | None = None

    async def load(self) -> PaperState:
        return self.new_state() if self.persisted is None else self.persisted.model_copy(deep=True)

    async def save(self, state: PaperState) -> None:
        self.persisted = state.model_copy(deep=True)

    async def reset(self, state: PaperState) -> None:
        fresh = self.new_state()
        fresh.sessions = list(state.sessions)
        self.persisted = fresh
