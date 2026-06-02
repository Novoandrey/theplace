"""Юниты корзины: расчёт суммы с опциями, слияние, изменение количества (конституция §5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cart.cart import (
    Cart,
    cart_total_kopecks,
    line_total_kopecks,
    line_unit_kopecks,
)
from src.menu.sources.json import JsonFileMenuSource

MENU_PATH = Path(__file__).resolve().parents[1] / "data" / "menu.json"


@pytest.fixture
async def menu():
    return await JsonFileMenuSource(MENU_PATH).get_menu()


async def test_unit_price_with_options(menu):
    # латте 300 + альт. молоко (+100) + сироп ваниль (+20) = 420 ₽ = 42000 коп
    cart = Cart()
    line = cart.add("latte", {"temp": "cold", "alt_milk": "alternative", "syrup": "vanilla"}, 2)
    assert line_unit_kopecks(menu, line) == 42000
    assert line_total_kopecks(menu, line) == 84000


async def test_zero_delta_options(menu):
    cart = Cart()
    line = cart.add("latte", {"temp": "hot", "alt_milk": "regular", "syrup": "none"}, 1)
    assert line_unit_kopecks(menu, line) == 30000


async def test_merge_same_options(menu):
    cart = Cart()
    cart.add("latte", {"temp": "hot"}, 1)
    cart.add("latte", {"temp": "hot"}, 1)
    assert len(cart.lines) == 1
    assert cart.lines[0].qty == 2


async def test_distinct_options_stay_separate(menu):
    cart = Cart()
    cart.add("latte", {"temp": "hot"}, 1)
    cart.add("latte", {"temp": "cold"}, 1)
    assert len(cart.lines) == 2


async def test_change_qty_and_remove(menu):
    cart = Cart()
    line = cart.add("bf_oatmeal", {}, 1)
    cart.change_qty(line.uid, 2)
    assert line.qty == 3
    cart.set_qty(line.uid, 0)
    assert cart.is_empty


async def test_cart_total(menu):
    cart = Cart()
    cart.add("latte", {"temp": "cold", "alt_milk": "alternative", "syrup": "vanilla"}, 2)  # 84000
    cart.add("bf_oatmeal", {}, 1)  # 35000
    assert cart_total_kopecks(menu, cart) == 119000


async def test_roundtrip_state(menu):
    cart = Cart()
    cart.add("latte", {"temp": "cold"}, 2)
    restored = Cart.from_state(cart.to_state())
    assert len(restored.lines) == 1
    assert restored.lines[0].qty == 2
    assert restored.seq == cart.seq
