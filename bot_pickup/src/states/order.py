"""FSM-состояния пути заказа (plan §8)."""

from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    registration = State()  # ввод имени (один раз)
    browsing = State()  # просмотр меню
    item_config = State()  # выбор опций позиции
    cart = State()  # корзина
    checkout = State()  # оформление
