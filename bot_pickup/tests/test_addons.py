"""Юниты допов (T068, FR-18): цена с допами и кол-вом, слияние, снапшот, стоп по допу."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cart.cart import (
    Cart,
    addons_snapshot,
    cart_total_kopecks,
    line_title,
    line_total_kopecks,
    line_unit_kopecks,
)
from src.menu.models import Category, Menu, MenuItem
from src.menu.sources.json import JsonFileMenuSource
from src.orders.service import OrderService, StopError

MENU_PATH = Path(__file__).resolve().parents[1] / "data" / "menu.json"


@pytest.fixture
async def menu():
    return await JsonFileMenuSource(MENU_PATH).get_menu()


async def test_price_with_addons_and_qty(menu):
    # Большой завтрак 750 + бекон 100 + 2×яйцо (50) = 950 ₽ за порцию; ×2 порции = 1900 ₽
    cart = Cart()
    line = cart.add("bf_big", {}, qty=2, addons={"add_bacon": 1, "add_egg": 2})
    assert line_unit_kopecks(menu, line) == 95000
    assert line_total_kopecks(menu, line) == 190000
    assert cart_total_kopecks(menu, cart) == 190000


async def test_addons_offered_only_to_food(menu):
    assert {a.id for a in menu.addon_items()}  # пул допов не пуст
    assert menu.addons_for(menu.item("bf_big"))  # завтраку допы предлагаются
    assert menu.addons_for(menu.item("latte")) == []  # напитку — нет
    assert menu.addons_for(menu.item("add_egg")) == []  # сам доп — нет


async def test_merge_respects_addons(menu):
    cart = Cart()
    cart.add("bf_big", {}, qty=1, addons={"add_bacon": 1})
    cart.add("bf_big", {}, qty=1, addons={"add_bacon": 1})
    assert len(cart.lines) == 1 and cart.lines[0].qty == 2
    cart.add("bf_big", {}, qty=1, addons={"add_bacon": 2})  # другое кол-во допа — отдельная строка
    assert len(cart.lines) == 2


async def test_addon_standalone_is_plain_item(menu):
    # доп можно заказать сам по себе как обычную позицию
    cart = Cart()
    line = cart.add("add_bacon", {}, qty=1)
    assert line_unit_kopecks(menu, line) == 10000
    assert line.addons == {}


async def test_line_title_shows_addons(menu):
    cart = Cart()
    line = cart.add("bf_big", {}, qty=1, addons={"add_bacon": 1, "add_egg": 2})
    title = line_title(menu, line)
    assert "Большой завтрак" in title
    assert "Бекон" in title
    assert "Яйцо ×2" in title


async def test_addons_snapshot(menu):
    cart = Cart()
    line = cart.add("bf_big", {}, qty=1, addons={"add_egg": 2})
    snap = addons_snapshot(menu, line)
    assert snap == [
        {
            "item_id": "add_egg",
            "title": "Яйцо",
            "qty": 2,
            "unit_price_kopecks": 5000,
            "total_kopecks": 10000,
        }
    ]


class _FakeSource:
    def __init__(self, menu: Menu) -> None:
        self._menu = menu

    async def get_menu(self, force_refresh: bool = False) -> Menu:
        return self._menu


async def test_stop_recheck_on_addon():
    # блюдо доступно, а доп — в стопе → заказ не создаётся
    menu = Menu(
        categories=[Category(id="food", title="Еда", sort=1)],
        items=[
            MenuItem(
                id="dish", category="food", title="Блюдо", price_kopecks=50000, available=True
            ),
            MenuItem(
                id="x", category="kitchen_addons", title="Доп", price_kopecks=5000, available=False
            ),
        ],
        addon_category="kitchen_addons",
    )
    cart = Cart()
    cart.add("dish", {}, qty=1, addons={"x": 1})
    service = OrderService(session=None, menu_source=_FakeSource(menu))
    with pytest.raises(StopError) as exc:
        await service.create_order(SimpleNamespace(id=1), cart)
    assert exc.value.item_title == "Доп"
