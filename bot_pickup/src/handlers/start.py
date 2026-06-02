"""Старт и регистрация (US-A3, FR-5): имя один раз, дальше — сразу в меню."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import ClientRepo
from src.handlers.menu import show_categories
from src.menu.sources.base import MenuSource
from src.states.order import OrderFlow
from src.texts import ru

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, session: AsyncSession, menu_source: MenuSource
) -> None:
    if message.from_user is None:
        return
    client = await ClientRepo(session).get_by_tg_id(message.from_user.id)
    if client is not None:
        await state.clear()
        await message.answer(ru.START_KNOWN.format(name=client.name))
        await show_categories(message, menu_source, state)
        return
    await state.set_state(OrderFlow.registration)
    await message.answer(ru.START_NEW)


@router.message(OrderFlow.registration)
async def got_name(
    message: Message, state: FSMContext, session: AsyncSession, menu_source: MenuSource
) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(ru.NAME_TOO_SHORT)
        return
    await ClientRepo(session).get_or_create(message.from_user.id, name)
    await state.clear()
    await message.answer(ru.NAME_SAVED.format(name=name))
    await show_categories(message, menu_source, state)
