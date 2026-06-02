"""ORM-модели (plan §4). Деньги — в копейках (int). Меню в БД не дублируем.

Статус заказа хранится строкой; допустимые значения — из app-enum `OrderStatus` (§9).
Строка вместо нативного PG ENUM — чтобы миграции не зависели от `ALTER TYPE`
(набор статусов контролируется приложением). Снапшоты (`*_snapshot`) фиксируют, что и
по какой цене заказали, чтобы меняющееся меню не мутировало прошлые заказы.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# JSONB на Postgres, обычный JSON — на прочих движках (для юнит-тестов на sqlite).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class OrderStatus(enum.StrEnum):
    """Жизненный цикл заказа (§9). `rejected` — терминальный."""

    new = "new"
    accepted = "accepted"
    almost_ready = "almost_ready"
    ready = "ready"
    handed_out = "handed_out"
    rejected = "rejected"


class PrintJobStatus(enum.StrEnum):
    pending = "pending"
    printed = "printed"
    failed = "failed"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list[Order]] = relationship(back_populates="client")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(8), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.new.value)
    pickup_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    menu_item_id: Mapped[str] = mapped_column(String(64))
    title_snapshot: Mapped[str] = mapped_column(String(256))
    unit_price_kopecks_snapshot: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)
    # Выбранные опции + дельты на момент заказа.
    options_snapshot: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    line_total_kopecks: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(64))  # tg_id сотрудника или "system"
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="status_history")


class PrintJob(Base):
    """Очередь печати (только для ESC/POS-пути, v0-print)."""

    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=PrintJobStatus.pending.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyCounter(Base):
    """Дневной счётчик для коротких номеров заказа (§4.1)."""

    __tablename__ = "daily_counter"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0)
