import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class InstrumentModel(TimestampMixin, Base):
    __tablename__ = "instruments"
    pair: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    margin_currency: Mapped[str] = mapped_column(String(10), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        Index("ix_market_candles_symbol_timeframe_timestamp", "pair", "timeframe", "open_time"),
        Index("ix_market_candles_timestamp", "open_time"),
        Index("ix_market_candles_symbol", "pair"),
    )
    pair: Mapped[str] = mapped_column(ForeignKey("instruments.pair"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(5), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    volume: Mapped[Decimal] = mapped_column(Numeric(36, 12))


class ScanRun(TimestampMixin, Base):
    __tablename__ = "scan_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20))
    total_markets: Mapped[int]
    eligible_markets: Mapped[int]
    rejected_markets: Mapped[int]
    opportunities: Mapped[list["OpportunityModel"]] = relationship(back_populates="scan_run")


class OpportunityModel(TimestampMixin, Base):
    __tablename__ = "opportunities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scan_runs.id"), index=True)
    pair: Mapped[str] = mapped_column(ForeignKey("instruments.pair"), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(30))
    metrics: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    scan_run: Mapped[ScanRun] = relationship(back_populates="opportunities")


class Trade(TimestampMixin, Base):
    __tablename__ = "trades"
    __table_args__ = (Index("ix_trades_pair_status", "pair", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mode: Mapped[str] = mapped_column(String(10))
    pair: Mapped[str] = mapped_column(String(40), index=True)
    strategy: Mapped[str] = mapped_column(String(50))
    strategy_version: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30))
    signal_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    entry: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    stop: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    target: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    leverage: Mapped[int]
    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_reason: Mapped[str | None] = mapped_column(String(50))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    fees: Mapped[Decimal] = mapped_column(Numeric(30, 12), default=0)
    slippage: Mapped[Decimal] = mapped_column(Numeric(30, 12), default=0)
    market_regime: Mapped[str] = mapped_column(String(30))
    indicator_snapshot: Mapped[dict] = mapped_column(JSON)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trades.id"))
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    order_type: Mapped[str] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30))
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemEvent(TimestampMixin, Base):
    __tablename__ = "system_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)


class PaperAccountRecord(TimestampMixin, Base):
    __tablename__ = "paper_accounts"
    account_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperSessionRecord(TimestampMixin, Base):
    __tablename__ = "paper_sessions"
    session_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperOrderRecord(TimestampMixin, Base):
    __tablename__ = "paper_orders"
    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperPositionRecord(TimestampMixin, Base):
    __tablename__ = "paper_positions"
    position_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    pair: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperTradeRecord(TimestampMixin, Base):
    __tablename__ = "paper_trades"
    trade_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(index=True)
    pair: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperSetupRecord(TimestampMixin, Base):
    __tablename__ = "paper_setups"
    setup_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PaperRuntimeRecord(TimestampMixin, Base):
    __tablename__ = "paper_runtime"
    key: Mapped[str] = mapped_column(String(30), primary_key=True, default="current")
    payload: Mapped[dict] = mapped_column(JSON)


class LiveRuntimeRecord(TimestampMixin, Base):
    __tablename__ = "live_runtime"
    key: Mapped[str] = mapped_column(String(30), primary_key=True, default="current")
    payload: Mapped[dict] = mapped_column(JSON)


class LiveExecutionRequestRecord(TimestampMixin, Base):
    __tablename__ = "live_execution_requests"
    execution_request_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    setup_id: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class LiveOrderRecord(TimestampMixin, Base):
    __tablename__ = "live_orders"
    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    execution_request_id: Mapped[uuid.UUID] = mapped_column(index=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class LivePositionRecord(TimestampMixin, Base):
    __tablename__ = "live_positions"
    position_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    exchange_position_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    pair: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    protection_status: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class LiveTradeRecord(TimestampMixin, Base):
    __tablename__ = "live_trades"
    trade_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    execution_request_id: Mapped[uuid.UUID] = mapped_column(index=True)
    pair: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class LiveAuditRecord(Base):
    __tablename__ = "live_audit_events"
    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    execution_request_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    payload: Mapped[dict] = mapped_column(JSON)
