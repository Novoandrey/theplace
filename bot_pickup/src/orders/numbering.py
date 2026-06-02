"""Короткий номер заказа (§4.1): дневной счётчик, формат NNN (>=1000 — без паддинга)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import DailyCounterRepo


def format_number(n: int) -> str:
    return f"{n:03d}" if n < 1000 else str(n)


async def next_order_number(session: AsyncSession, today: date | None = None) -> str:
    n = await DailyCounterRepo(session).next_number(today or date.today())
    return format_number(n)
