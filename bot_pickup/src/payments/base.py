"""Контракт оплаты (plan §7). В MVP оплаты нет (NoPayment); Точка СБП — v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.db.models import Order


@dataclass(slots=True)
class PaymentResult:
    paid: bool
    payment_url: str | None = None
    detail: str | None = None


@runtime_checkable
class PaymentProvider(Protocol):
    async def create_payment(self, order: Order) -> PaymentResult: ...
