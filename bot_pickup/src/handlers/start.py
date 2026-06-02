"""Старт и регистрация (US-A3, FR-5): имя спрашиваем один раз, дальше переиспользуем.

Реализовано в Фазе 1, т.к. чекпойнт фазы требует рабочего `/start`. Меню после
регистрации подключим в Группе A (Browsing).
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import ClientRepo
from src.states.order import OrderFlow
from src.texts import ru

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    client = await ClientRepo(session).get_by_tg_id(message.from_user.id)
    if client is not None:
        await state.clear()
        await message.answer(ru.START_KNOWN.format(name=client.name))
        return
    await state.set_state(OrderFlow.registration)
    await message.answer(ru.START_NEW)


@router.message(OrderFlow.registration)
async def got_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(ru.NAME_TOO_SHORT)
        return
    await ClientRepo(session).get_or_create(message.from_user.id, name)
    await state.clear()
    await message.answer(ru.NAME_SAVED.format(name=name))
