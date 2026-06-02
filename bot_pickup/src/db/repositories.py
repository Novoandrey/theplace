"""Репозитории — тонкий слой доступа к данным (plan §4, §10).

Позиции заказа (`order_items`) пишутся через relationship `Order.items` (cascade),
поэтому отдельного репозитория для них нет.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Client, DailyCounter, Order, OrderStatus, OrderStatusHistory

# Статусы, после которых заказ больше не активен.
_TERMINAL = (OrderStatus.handed_out.value, OrderStatus.rejected.value)


class ClientRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_tg_id(self, tg_user_id: int) -> Client | None:
        stmt = select(Client).where(Client.tg_user_id == tg_user_id)
        return await self.session.scalar(stmt)

    async def get_or_create(self, tg_user_id: int, name: str) -> Client:
        """Имя спрашиваем один раз (FR-5). Идемпотентно к гонке через ON CONFLICT."""
        existing = await self.get_by_tg_id(tg_user_id)
        if existing is not None:
            return existing
        stmt = (
            pg_insert(Client)
            .values(tg_user_id=tg_user_id, name=name)
            .on_conflict_do_nothing(index_elements=[Client.tg_user_id])
        )
        await self.session.execute(stmt)
        await self.session.flush()
        client = await self.get_by_tg_id(tg_user_id)
        assert client is not None  # после insert/on-conflict строка точно есть
        return client


class OrderRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, order: Order) -> None:
        self.session.add(order)

    async def get(self, order_id: uuid.UUID) -> Order | None:
        return await self.session.get(Order, order_id)

    async def list_for_client(self, client_id: int) -> list[Order]:
        stmt = select(Order).where(Order.client_id == client_id).order_by(Order.created_at.desc())
        return list(await self.session.scalars(stmt))

    async def get_active_for_client(self, client_id: int) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.client_id == client_id, Order.status.not_in(_TERMINAL))
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)


class StatusHistoryRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, order_id: uuid.UUID, status: str, actor: str, note: str | None = None) -> None:
        self.session.add(
            OrderStatusHistory(order_id=order_id, status=status, actor=actor, note=note)
        )


class DailyCounterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_number(self, day: date) -> int:
        """Атомарно увеличивает дневной счётчик и возвращает новое значение (§4.1)."""
        stmt = (
            pg_insert(DailyCounter)
            .values(day=day, last_number=1)
            .on_conflict_do_update(
                index_elements=[DailyCounter.day],
                set_={"last_number": DailyCounter.last_number + 1},
            )
            .returning(DailyCounter.last_number)
        )
        return await self.session.scalar(stmt)
