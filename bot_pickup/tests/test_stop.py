"""Юнит перепроверки стопа (FR-16): позиция в стопе — заказ не создаётся.

Проверка стопа идёт до обращения к БД, поэтому тест обходится без сессии (session=None).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.cart.cart import Cart
from src.menu.models import Category, Menu, MenuItem
from src.orders.service import OrderService, StopError


class _FakeMenuSource:
    def __init__(self, menu: Menu) -> None:
        self._menu = menu

    async def get_menu(self, force_refresh: bool = False) -> Menu:
        return self._menu


def _menu_with_stopped_item() -> Menu:
    return Menu(
        categories=[Category(id="c", title="Кат", sort=1)],
        option_groups={},
        items=[MenuItem(id="x", category="c", title="Икс", price_kopecks=10000, available=False)],
    )


async def test_stopped_item_blocks_order():
    cart = Cart()
    cart.add("x", {}, 1)
    service = OrderService(session=None, menu_source=_FakeMenuSource(_menu_with_stopped_item()))
    with pytest.raises(StopError) as exc:
        await service.create_order(SimpleNamespace(id=1), cart)
    assert exc.value.item_title == "Икс"


async def test_missing_item_blocks_order():
    cart = Cart()
    cart.add("ghost", {}, 1)  # позиции нет в меню вовсе
    service = OrderService(session=None, menu_source=_FakeMenuSource(_menu_with_stopped_item()))
    with pytest.raises(StopError):
        await service.create_order(SimpleNamespace(id=1), cart)
