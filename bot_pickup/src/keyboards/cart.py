"""Клавиатура корзины и callback-данные (T026)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.cart.cart import Cart
from src.keyboards.common import CB_CART, CB_HOME
from src.texts import ru


class CartQtyCB(CallbackData, prefix="cq"):
    uid: int
    delta: int  # -1 / 0 / +1


class CartDelCB(CallbackData, prefix="cd"):
    uid: int


class CheckoutCB(CallbackData, prefix="co"):
    pass


class ConfirmCB(CallbackData, prefix="cy"):
    pass


def kb_cart(cart: Cart) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for line in cart.lines:
        b.row(
            InlineKeyboardButton(text="−", callback_data=CartQtyCB(uid=line.uid, delta=-1).pack()),
            InlineKeyboardButton(
                text=f"{line.qty} шт", callback_data=CartQtyCB(uid=line.uid, delta=0).pack()
            ),
            InlineKeyboardButton(text="+", callback_data=CartQtyCB(uid=line.uid, delta=1).pack()),
            InlineKeyboardButton(text=ru.BTN_DELETE, callback_data=CartDelCB(uid=line.uid).pack()),
        )
    if not cart.is_empty:
        b.row(InlineKeyboardButton(text=ru.BTN_CHECKOUT, callback_data=CheckoutCB().pack()))
    b.row(InlineKeyboardButton(text=ru.BTN_MENU, callback_data=CB_HOME))
    return b.as_markup()


def kb_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=ru.BTN_CONFIRM, callback_data=ConfirmCB().pack()))
    b.row(InlineKeyboardButton(text=ru.BTN_BACK, callback_data=CB_CART))
    return b.as_markup()
