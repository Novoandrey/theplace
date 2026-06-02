"""Общие помощники хендлеров: рендер экрана (edit/send) и работа с корзиной в FSM."""

from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from src.cart.cart import Cart


async def render(
    event: TelegramObject, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    """Для callback — редактируем текущее сообщение; для message — отправляем новое."""
    if isinstance(event, CallbackQuery):
        if event.message is not None:
            try:
                await event.message.edit_text(text, reply_markup=markup)
            except TelegramBadRequest:
                pass  # «message is not modified» и т.п. — не критично
        await event.answer()
    elif isinstance(event, Message):
        await event.answer(text, reply_markup=markup)


async def get_cart(state: FSMContext) -> Cart:
    data = await state.get_data()
    return Cart.from_state(data.get("cart"))


async def save_cart(state: FSMContext, cart: Cart) -> None:
    await state.update_data(cart=cart.to_state())
