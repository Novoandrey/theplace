"""Хендлеры меню (T020) и выбора опций позиции (T024).

Поток: категории → позиции категории → карточка позиции → (опции) → добавить в корзину.
Стоп-позиции (`available=false`) не показываются (FR-4).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.handlers.common import get_cart, render, save_cart
from src.keyboards import menu as kb
from src.keyboards.common import CB_HOME
from src.menu.sources.base import MenuSource
from src.states.order import OrderFlow
from src.texts import ru

router = Router(name="menu")


async def show_categories(
    event: TelegramObject, menu_source: MenuSource, state: FSMContext
) -> None:
    menu = await menu_source.get_menu()
    await state.set_state(OrderFlow.browsing)
    await render(event, ru.MENU_TITLE, kb.kb_categories(menu))


async def _show_category(
    event: TelegramObject, menu_source: MenuSource, state: FSMContext, category_id: str
) -> None:
    menu = await menu_source.get_menu()
    category = next((c for c in menu.categories if c.id == category_id), None)
    title = category.title if category else ru.MENU_TITLE
    items = menu.items_in(category_id)
    text = title if items else f"{title}\n\n{ru.CATEGORY_EMPTY}"
    await state.set_state(OrderFlow.browsing)
    await render(event, text, kb.kb_category(menu, category_id))


@router.callback_query(F.data == CB_HOME)
async def nav_home(cb: CallbackQuery, menu_source: MenuSource, state: FSMContext) -> None:
    await show_categories(cb, menu_source, state)


@router.callback_query(kb.CategoryCB.filter())
async def open_category(
    cb: CallbackQuery, callback_data: kb.CategoryCB, menu_source: MenuSource, state: FSMContext
) -> None:
    await _show_category(cb, menu_source, state, callback_data.id)


@router.callback_query(kb.ItemCB.filter())
async def open_item(
    cb: CallbackQuery, callback_data: kb.ItemCB, menu_source: MenuSource, state: FSMContext
) -> None:
    menu = await menu_source.get_menu()
    item = menu.item(callback_data.id)
    if item is None or not item.available:
        await cb.answer(ru.ITEM_GONE, show_alert=True)
        await _show_category(cb, menu_source, state, item.category if item else "")
        return
    if item.options:
        defaults = {
            gid: menu.group(gid).choices[0].id
            for gid in item.options
            if menu.group(gid) and menu.group(gid).choices
        }
        await state.set_state(OrderFlow.item_config)
        await state.update_data(cfg={"item_id": item.id, "options": defaults})
        await render(
            cb, kb.item_card_text(menu, item, defaults), kb.kb_item_card(menu, item, defaults)
        )
    else:
        await render(cb, kb.item_card_text(menu, item, {}), kb.kb_item_card(menu, item, {}))


@router.callback_query(kb.OptPickCB.filter())
async def pick_option(
    cb: CallbackQuery, callback_data: kb.OptPickCB, menu_source: MenuSource, state: FSMContext
) -> None:
    data = await state.get_data()
    cfg = data.get("cfg")
    if not cfg:
        await cb.answer()
        return
    cfg["options"][callback_data.group] = callback_data.choice
    await state.update_data(cfg=cfg)
    menu = await menu_source.get_menu()
    item = menu.item(cfg["item_id"])
    if item is None:
        await cb.answer()
        return
    await render(
        cb,
        kb.item_card_text(menu, item, cfg["options"]),
        kb.kb_item_card(menu, item, cfg["options"]),
    )


@router.callback_query(kb.AddCB.filter())
async def add_item(
    cb: CallbackQuery, callback_data: kb.AddCB, menu_source: MenuSource, state: FSMContext
) -> None:
    menu = await menu_source.get_menu()
    item = menu.item(callback_data.id)
    if item is None or not item.available:
        await cb.answer(ru.ITEM_GONE, show_alert=True)
        return
    cart = await get_cart(state)
    cart.add(item.id, {}, 1)
    await save_cart(state, cart)
    await cb.answer(ru.ADDED)
    await _show_category(cb, menu_source, state, item.category)


@router.callback_query(kb.AddConfiguredCB.filter())
async def add_configured(cb: CallbackQuery, menu_source: MenuSource, state: FSMContext) -> None:
    data = await state.get_data()
    cfg = data.get("cfg")
    if not cfg:
        await cb.answer()
        return
    menu = await menu_source.get_menu()
    item = menu.item(cfg["item_id"])
    if item is None or not item.available:
        await cb.answer(ru.ITEM_GONE, show_alert=True)
        return
    cart = await get_cart(state)
    cart.add(item.id, cfg["options"], 1)
    await save_cart(state, cart)
    await state.update_data(cfg=None)
    await cb.answer(ru.ADDED)
    await _show_category(cb, menu_source, state, item.category)


@router.message(F.text == "/menu")
async def cmd_menu(message: Message, menu_source: MenuSource, state: FSMContext) -> None:
    await show_categories(message, menu_source, state)
