"""Хендлер управления заказом в чате сотрудников (T034, US-B2/B3).

Кнопки переключают статус по машине (T033), пишут историю и (для значимых статусов)
уведомляют клиента. Отклонение — выбором причины. Работает только в чате сотрудников.
"""

from __future__ import annotations

import uuid

from aiogram import Bot, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Client, Order, OrderStatus
from src.db.repositories import OrderRepo, StatusHistoryRepo
from src.handlers.common import edit_message
from src.handlers.status import notify_client
from src.keyboards.staff import (
    StaffRejectCB,
    StaffRejectReasonCB,
    StaffStatusCB,
    kb_reject_reasons,
    kb_staff,
)
from src.orders.sinks.telegram_staff import format_staff_ticket
from src.orders.status import NOTIFY_CLIENT, InvalidTransition, assert_transition
from src.texts import ru

router = Router(name="staff")


def _in_staff_chat(cb: CallbackQuery, staff_chat_id: int) -> bool:
    return cb.message is not None and cb.message.chat.id == staff_chat_id


async def _load(session: AsyncSession, order_hex: str) -> Order | None:
    try:
        order_id = uuid.UUID(hex=order_hex)
    except ValueError:
        return None
    return await OrderRepo(session).get_full(order_id)


async def _apply(
    cb: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    order: Order,
    target: OrderStatus,
    note: str | None = None,
) -> None:
    current = OrderStatus(order.status)
    try:
        assert_transition(current, target)
    except InvalidTransition:
        await edit_message(cb, format_staff_ticket(order), kb_staff(order.id, current))
        await cb.answer(ru.STATUS_OUTDATED)
        return
    order.status = target.value
    StatusHistoryRepo(session).add(order.id, target.value, str(cb.from_user.id), note)
    await session.flush()
    if target in NOTIFY_CLIENT:
        client = await session.get(Client, order.client_id)
        if client is not None:
            await notify_client(bot, client.tg_user_id, order.order_number, target, note)
    await edit_message(cb, format_staff_ticket(order), kb_staff(order.id, target))
    await cb.answer(ru.STATUS_SET.format(label=ru.STATUS_LABELS.get(target.value, target.value)))


@router.callback_query(StaffStatusCB.filter())
async def set_status(
    cb: CallbackQuery,
    callback_data: StaffStatusCB,
    session: AsyncSession,
    bot: Bot,
    staff_chat_id: int,
) -> None:
    if not _in_staff_chat(cb, staff_chat_id):
        await cb.answer()
        return
    order = await _load(session, callback_data.order)
    if order is None:
        await cb.answer(ru.ORDER_NOT_FOUND, show_alert=True)
        return
    await _apply(cb, session, bot, order, OrderStatus(callback_data.status))


@router.callback_query(StaffRejectCB.filter())
async def ask_reason(
    cb: CallbackQuery, callback_data: StaffRejectCB, session: AsyncSession, staff_chat_id: int
) -> None:
    if not _in_staff_chat(cb, staff_chat_id):
        await cb.answer()
        return
    order = await _load(session, callback_data.order)
    if order is None:
        await cb.answer(ru.ORDER_NOT_FOUND, show_alert=True)
        return
    await edit_message(cb, format_staff_ticket(order), kb_reject_reasons(order.id))
    await cb.answer()


@router.callback_query(StaffRejectReasonCB.filter())
async def do_reject(
    cb: CallbackQuery,
    callback_data: StaffRejectReasonCB,
    session: AsyncSession,
    bot: Bot,
    staff_chat_id: int,
) -> None:
    if not _in_staff_chat(cb, staff_chat_id):
        await cb.answer()
        return
    order = await _load(session, callback_data.order)
    if order is None:
        await cb.answer(ru.ORDER_NOT_FOUND, show_alert=True)
        return
    if callback_data.code == "_cancel":
        await edit_message(
            cb, format_staff_ticket(order), kb_staff(order.id, OrderStatus(order.status))
        )
        await cb.answer()
        return
    reason = ru.REJECT_REASONS.get(callback_data.code, ru.REJECT_REASONS["other"])
    await _apply(cb, session, bot, order, OrderStatus.rejected, note=reason)
