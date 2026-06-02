"""Уведомление клиента о смене статуса (T042, US-C2, FR-9/10/11).

Триггерится из хендлера сотрудника при значимых сменах статуса. Шлёт в тот же чат,
где клиент оформлял (его личный чат с ботом — `clients.tg_user_id`).
"""

from __future__ import annotations

import logging

from aiogram import Bot

from src.db.models import OrderStatus
from src.texts import ru

logger = logging.getLogger(__name__)


async def notify_client(
    bot: Bot, chat_id: int, order_number: str, status: OrderStatus, note: str | None = None
) -> None:
    template = ru.CLIENT_STATUS_MSG.get(status.value)
    if template is None:
        return
    text = template.format(number=order_number, reason=note or "")
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("notify client %s failed (order %s)", chat_id, order_number)
