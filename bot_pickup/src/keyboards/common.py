"""Базовая навигация: «назад», «в начало», «корзина». Без тупиков (конституция §7, FR-13).

Хендлеры конкретных экранов (меню/корзина/оформление) появятся в Группах A–C; здесь —
переиспользуемые кнопки и единые callback-данные, чтобы навигация была консистентной.
"""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.texts import ru

CB_HOME = "nav:home"
CB_BACK = "nav:back"
CB_CART = "nav:cart"


def btn_home() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=ru.BTN_HOME, callback_data=CB_HOME)


def btn_back(target: str = CB_BACK) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=ru.BTN_BACK, callback_data=target)


def btn_cart() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=ru.BTN_CART, callback_data=CB_CART)


def with_nav(
    builder: InlineKeyboardBuilder,
    *,
    back: str | None = None,
    cart: bool = False,
    home: bool = True,
) -> InlineKeyboardBuilder:
    """Добавляет к клавиатуре строку навигации. Всегда есть путь назад/в начало."""
    row: list[InlineKeyboardButton] = []
    if back is not None:
        row.append(btn_back(back))
    if cart:
        row.append(btn_cart())
    if home:
        row.append(btn_home())
    if row:
        builder.row(*row)
    return builder
