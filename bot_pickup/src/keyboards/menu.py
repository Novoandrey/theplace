"""Клавиатуры меню и callback-данные (T020/T021/T024).

Экраны: список категорий → позиции категории → карточка позиции (с выбором опций).
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.cart.cart import configured_unit_kopecks, format_kopecks
from src.keyboards.common import CB_CART, CB_HOME
from src.menu.models import Menu, MenuItem
from src.texts import ru


class CategoryCB(CallbackData, prefix="cat"):
    id: str


class ItemCB(CallbackData, prefix="item"):
    id: str


class AddCB(CallbackData, prefix="add"):
    id: str  # добавить позицию без опций/допов


class OptPickCB(CallbackData, prefix="opt"):
    group: str
    choice: str


class AddonStepCB(CallbackData, prefix="adn"):
    addon: str
    delta: int  # -1 / 0 / +1


class AddConfiguredCB(CallbackData, prefix="addc"):
    pass  # добавить настроенную позицию из карточки


def kb_categories(menu: Menu) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in menu.categories_sorted():
        b.button(text=c.title, callback_data=CategoryCB(id=c.id))
    b.adjust(2)
    b.row(InlineKeyboardButton(text=ru.BTN_CART, callback_data=CB_CART))
    return b.as_markup()


def kb_category(menu: Menu, category_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for it in menu.items_in(category_id):
        b.button(text=it.title, callback_data=ItemCB(id=it.id))
    b.adjust(1)
    b.row(
        InlineKeyboardButton(text=ru.BTN_BACK, callback_data=CB_HOME),
        InlineKeyboardButton(text=ru.BTN_CART, callback_data=CB_CART),
    )
    return b.as_markup()


def kb_item_card(
    menu: Menu, item: MenuItem, options: dict[str, str], addons: dict[str, int]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    has_config = False
    for gid in item.options:
        group = menu.group(gid)
        if group is None:
            continue
        row: list[InlineKeyboardButton] = []
        for ch in group.choices:
            mark = ru.MARK_SELECTED if options.get(gid) == ch.id else ""
            row.append(
                InlineKeyboardButton(
                    text=mark + ch.title,
                    callback_data=OptPickCB(group=gid, choice=ch.id).pack(),
                )
            )
        b.row(*row)
        has_config = True
    for addon in menu.addons_for(item):
        q = addons.get(addon.id, 0)
        label = f"{addon.title} +{addon.price_kopecks // 100}₽"
        if q:
            label += f" · {q}"
        b.row(
            InlineKeyboardButton(
                text="−", callback_data=AddonStepCB(addon=addon.id, delta=-1).pack()
            ),
            InlineKeyboardButton(
                text=label, callback_data=AddonStepCB(addon=addon.id, delta=0).pack()
            ),
            InlineKeyboardButton(
                text="+", callback_data=AddonStepCB(addon=addon.id, delta=1).pack()
            ),
        )
        has_config = True
    if has_config:
        b.row(InlineKeyboardButton(text=ru.BTN_ADD_CART, callback_data=AddConfiguredCB().pack()))
    else:
        b.row(InlineKeyboardButton(text=ru.BTN_ADD, callback_data=AddCB(id=item.id).pack()))
    b.row(
        InlineKeyboardButton(text=ru.BTN_BACK, callback_data=CategoryCB(id=item.category).pack()),
        InlineKeyboardButton(text=ru.BTN_CART, callback_data=CB_CART),
        InlineKeyboardButton(text=ru.BTN_HOME, callback_data=CB_HOME),
    )
    return b.as_markup()


def item_card_text(
    menu: Menu, item: MenuItem, options: dict[str, str], addons: dict[str, int]
) -> str:
    parts = [item.title]
    if item.serving:
        parts.append(item.serving)
    parts.append(format_kopecks(configured_unit_kopecks(menu, item.id, options, addons)))
    text = " · ".join(parts)
    if item.description:
        text += f"\n{item.description}"
    return text
