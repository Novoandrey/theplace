"""Хендлеры оформления (T030): подтверждение → создание заказа → номер клиенту.

Перепроверка стопа (FR-16) — внутри OrderService. После создания заказ уходит в каналы
доставки (Группа B добавит TelegramStaffChat). Защита от двойного «Подтвердить»: после
успеха корзина очищается, повторное подтверждение находит пустую корзину.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.cart.cart import Cart, format_cart
from src.db.repositories import ClientRepo
from src.handlers.common import edit_message, get_cart, render, save_cart
from src.keyboards.cart import CheckoutCB, ConfirmCB, kb_cart, kb_confirm
from src.keyboards.common import kb_to_menu
from src.menu.sources.base import MenuSource
from src.orders.service import OrderService, StopError, dispatch_order
from src.orders.sinks.base import OrderSink
from src.states.order import OrderFlow
from src.texts import ru

router = Router(name="checkout")


@router.callback_query(CheckoutCB.filter())
async def checkout(cb: CallbackQuery, menu_source: MenuSource, state: FSMContext) -> None:
    cart = await get_cart(state)
    if cart.is_empty:
        await cb.answer(ru.CART_EMPTY, show_alert=True)
        return
    menu = await menu_source.get_menu()
    await state.set_state(OrderFlow.checkout)
    await render(cb, f"{format_cart(menu, cart)}\n\n{ru.CONFIRM_Q}", kb_confirm())


@router.callback_query(ConfirmCB.filter())
async def confirm(
    cb: CallbackQuery,
    session: AsyncSession,
    menu_source: MenuSource,
    state: FSMContext,
    order_sinks: list[OrderSink],
) -> None:
    cart = await get_cart(state)
    if cart.is_empty:
        await cb.answer(ru.ORDER_ALREADY, show_alert=True)
        return
    if cb.from_user is None:
        await cb.answer()
        return
    client = await ClientRepo(session).get_by_tg_id(cb.from_user.id)
    if client is None:
        await render(cb, ru.NEED_START)
        return

    # Тяжёлая операция (запись заказа + перепроверка стопа + доставка на кухню, конституция §8):
    # гасим спиннер, показываем индикатор, убираем кнопку «Подтвердить» (и от двойного нажатия).
    await cb.answer()
    await edit_message(cb, ru.ORDER_PROCESSING)

    service = OrderService(session, menu_source)
    try:
        order = await service.create_order(client, cart)
    except StopError as exc:
        menu = await menu_source.get_menu(force_refresh=True)
        text = f"{ru.STOP_ITEM.format(title=exc.item_title)}\n\n{format_cart(menu, cart)}"
        await edit_message(cb, text, kb_cart(cart))
        return

    await save_cart(state, Cart())
    await state.update_data(cfg=None)
    await state.set_state(OrderFlow.browsing)
    await dispatch_order(order, order_sinks)
    await edit_message(cb, ru.ORDER_DONE.format(number=order.order_number), kb_to_menu())
