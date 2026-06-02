"""Клавиатуры управления заказом в чате сотрудников (T035)."""

from __future__ import annotations

import uuid

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.models import OrderStatus
from src.orders.status import next_statuses
from src.texts import ru


class StaffStatusCB(CallbackData, prefix="st"):
    order: str  # uuid hex
    status: str  # целевой статус (значение)


class StaffRejectCB(CallbackData, prefix="rj"):
    order: str


class StaffRejectReasonCB(CallbackData, prefix="rjr"):
    order: str
    code: str


def kb_staff(order_id: uuid.UUID, current: OrderStatus) -> InlineKeyboardMarkup | None:
    """Кнопки следующих статусов + «Отклонить». None — заказ терминальный (кнопок нет)."""
    oid = order_id.hex
    b = InlineKeyboardBuilder()
    nexts = next_statuses(current)
    has_buttons = False
    for nxt in nexts:
        if nxt == OrderStatus.rejected:
            continue  # отклонение — отдельной кнопкой (с причиной)
        b.button(
            text=ru.STATUS_ACTION[nxt.value],
            callback_data=StaffStatusCB(order=oid, status=nxt.value),
        )
        has_buttons = True
    if OrderStatus.rejected in nexts:
        b.button(text=ru.BTN_REJECT, callback_data=StaffRejectCB(order=oid))
        has_buttons = True
    b.adjust(1)
    return b.as_markup() if has_buttons else None


def kb_reject_reasons(order_id: uuid.UUID) -> InlineKeyboardMarkup:
    oid = order_id.hex
    b = InlineKeyboardBuilder()
    for code, title in ru.REJECT_REASONS.items():
        b.button(text=title, callback_data=StaffRejectReasonCB(order=oid, code=code))
    b.button(text=ru.BTN_CANCEL, callback_data=StaffRejectReasonCB(order=oid, code="_cancel"))
    b.adjust(1)
    return b.as_markup()
