"""Контракт канала доставки заказа на кухню (plan §6).

Конкретные реализации (TelegramStaffChat — всегда; EscPosPrinter — v0-print, путь C;
QuickRestoTerminal — v1.1, путь A) появятся в соответствующих фазах. Абстракция позволяет
строить на моке/Telegram-чате и переключать канал без правки бизнес-логики (конституция §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.db.models import Order


@dataclass(slots=True)
class SinkResult:
    ok: bool
    detail: str | None = None


@runtime_checkable
class OrderSink(Protocol):
    name: str

    async def send(self, order: Order) -> SinkResult: ...
