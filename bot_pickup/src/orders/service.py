"""Создание заказа (T029) и фан-аут в каналы доставки (plan §3, §6, §8).

Перед созданием — перепроверка стопа по свежему меню (FR-16): если позиция ушла в стоп,
заказ не создаётся (StopError). Позиции и цены фиксируются снапшотами.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.cart.cart import (
    Cart,
    addons_snapshot,
    cart_total_kopecks,
    line_total_kopecks,
    line_unit_kopecks,
    options_snapshot,
)
from src.db.models import Order, OrderItem, OrderStatus
from src.db.repositories import StatusHistoryRepo
from src.menu.sources.base import MenuSource
from src.orders.numbering import next_order_number

if TYPE_CHECKING:
    from src.db.models import Client
    from src.orders.sinks.base import OrderSink

logger = logging.getLogger(__name__)


class StopError(Exception):
    """Позиция корзины ушла в стоп — заказ не создаётся (FR-16)."""

    def __init__(self, item_title: str) -> None:
        super().__init__(item_title)
        self.item_title = item_title


class OrderService:
    def __init__(self, session: AsyncSession, menu_source: MenuSource) -> None:
        self.session = session
        self.menu_source = menu_source

    async def create_order(self, client: Client, cart: Cart) -> Order:
        menu = await self.menu_source.get_menu(force_refresh=True)  # FR-16: свежие данные

        for line in cart.lines:
            item = menu.item(line.item_id)
            if item is None or not item.available:
                raise StopError(item.title if item is not None else line.item_id)
            for aid in line.addons:
                addon = menu.item(aid)
                if addon is None or not addon.available:
                    raise StopError(addon.title if addon is not None else aid)

        number = await next_order_number(self.session)
        order = Order(
            id=uuid.uuid4(),
            order_number=number,
            client_id=client.id,
            status=OrderStatus.new.value,
            total_kopecks=cart_total_kopecks(menu, cart),
        )
        order.client = client  # чтобы тикет кухни читал имя без отдельного запроса
        for line in cart.lines:
            item = menu.item(line.item_id)
            order.items.append(
                OrderItem(
                    menu_item_id=line.item_id,
                    title_snapshot=item.title if item else line.item_id,
                    unit_price_kopecks_snapshot=line_unit_kopecks(menu, line),
                    qty=line.qty,
                    options_snapshot=options_snapshot(menu, line) or None,
                    addons_snapshot=addons_snapshot(menu, line) or None,
                    line_total_kopecks=line_total_kopecks(menu, line),
                )
            )
        self.session.add(order)
        await self.session.flush()
        StatusHistoryRepo(self.session).add(order.id, OrderStatus.new.value, "system")
        return order


async def dispatch_order(order: Order, sinks: list[OrderSink]) -> None:
    """Фан-аут заказа по включённым каналам доставки. Падение одного канала не валит остальные."""
    for sink in sinks:
        try:
            await sink.send(order)
        except Exception:
            logger.exception("sink %s failed for order %s", getattr(sink, "name", sink), order.id)
