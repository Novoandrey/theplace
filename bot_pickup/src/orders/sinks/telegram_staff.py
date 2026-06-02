"""TelegramStaffChatSink (T032) — всегда включённый канал доставки заказа на кухню (FR-15).

Шлёт читаемый тикет в чат сотрудников с inline-кнопками статусов. Падение отправки
возвращается как `SinkResult(ok=False)` и не валит оформление (см. `dispatch_order`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cart.cart import format_kopecks
from src.db.models import OrderStatus
from src.keyboards.staff import kb_staff
from src.orders.sinks.base import SinkResult
from src.texts import ru

if TYPE_CHECKING:
    from aiogram import Bot

    from src.db.models import Order

_SILENT_CHOICES = {"regular", "none"}


def _format_options(snapshot: list[dict] | None) -> str:
    if not snapshot:
        return ""
    titles = [o["choice_title"] for o in snapshot if o.get("choice") not in _SILENT_CHOICES]
    return f" ({', '.join(titles)})" if titles else ""


def format_staff_ticket(order: Order, *, with_status: bool = True) -> str:
    head = f"Заказ {order.order_number}"
    if with_status:
        head += f" · {ru.STATUS_LABELS.get(order.status, order.status)}"
    rows = [head, ru.STAFF_NAME.format(name=order.client.name), ""]
    for i, it in enumerate(order.items, 1):
        opts = _format_options(it.options_snapshot)
        rows.append(
            f"{i}. {it.title_snapshot}{opts} × {it.qty} — {format_kopecks(it.line_total_kopecks)}"
        )
    rows.append("")
    rows.append(ru.CART_TOTAL.format(total=format_kopecks(order.total_kopecks)))
    return "\n".join(rows)


class TelegramStaffChatSink:
    name = "telegram"

    def __init__(self, bot: Bot, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id

    async def send(self, order: Order) -> SinkResult:
        try:
            await self.bot.send_message(
                self.chat_id,
                format_staff_ticket(order),
                reply_markup=kb_staff(order.id, OrderStatus(order.status)),
            )
        except Exception as exc:  # кухня-чат недоступна — не валим заказ
            return SinkResult(ok=False, detail=str(exc))
        return SinkResult(ok=True)
