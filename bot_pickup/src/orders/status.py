"""Машина статусов заказа (T033, plan §9).

Линейная цепочка `new → accepted → almost_ready → ready → handed_out`; ветка `rejected`
(с причиной) доступна с любого нетерминального статуса до готовности и терминальна.
Каждая смена пишется в `order_status_history` (делает вызывающий код).
"""

from __future__ import annotations

from src.db.models import OrderStatus

# Разрешённые переходы: текущий статус -> допустимые следующие.
ALLOWED: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.new: (OrderStatus.accepted, OrderStatus.rejected),
    OrderStatus.accepted: (OrderStatus.almost_ready, OrderStatus.rejected),
    OrderStatus.almost_ready: (OrderStatus.ready, OrderStatus.rejected),
    OrderStatus.ready: (OrderStatus.handed_out,),
    OrderStatus.handed_out: (),
    OrderStatus.rejected: (),
}

# Терминальные статусы (заказ больше не активен).
TERMINAL = frozenset({OrderStatus.handed_out, OrderStatus.rejected})

# Статусы, о которых уведомляем клиента (FR-9/10/11).
NOTIFY_CLIENT = frozenset(
    {OrderStatus.accepted, OrderStatus.almost_ready, OrderStatus.ready, OrderStatus.rejected}
)


class InvalidTransition(Exception):
    def __init__(self, current: OrderStatus, target: OrderStatus) -> None:
        super().__init__(f"{current.value} -> {target.value}")
        self.current = current
        self.target = target


def next_statuses(current: OrderStatus) -> tuple[OrderStatus, ...]:
    return ALLOWED.get(current, ())


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ALLOWED.get(current, ())


def assert_transition(current: OrderStatus, target: OrderStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(current, target)
