"""Хендлеры корзины (T025): просмотр, изменение количества, удаление."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.cart.cart import format_cart
from src.handlers.common import get_cart, render, save_cart
from src.keyboards.cart import CartDelCB, CartQtyCB, kb_cart
from src.keyboards.common import CB_CART
from src.menu.sources.base import MenuSource
from src.states.order import OrderFlow

router = Router(name="cart")


async def _show_cart(cb: CallbackQuery, menu_source: MenuSource, state: FSMContext) -> None:
    menu = await menu_source.get_menu()
    cart = await get_cart(state)
    await state.set_state(OrderFlow.cart)
    await render(cb, format_cart(menu, cart), kb_cart(cart))


@router.callback_query(F.data == CB_CART)
async def open_cart(cb: CallbackQuery, menu_source: MenuSource, state: FSMContext) -> None:
    await _show_cart(cb, menu_source, state)


@router.callback_query(CartQtyCB.filter())
async def change_qty(
    cb: CallbackQuery, callback_data: CartQtyCB, menu_source: MenuSource, state: FSMContext
) -> None:
    cart = await get_cart(state)
    if callback_data.delta:
        cart.change_qty(callback_data.uid, callback_data.delta)
        await save_cart(state, cart)
    await _show_cart(cb, menu_source, state)


@router.callback_query(CartDelCB.filter())
async def delete_line(
    cb: CallbackQuery, callback_data: CartDelCB, menu_source: MenuSource, state: FSMContext
) -> None:
    cart = await get_cart(state)
    cart.remove(callback_data.uid)
    await save_cart(state, cart)
    await _show_cart(cb, menu_source, state)
