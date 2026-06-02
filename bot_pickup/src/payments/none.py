"""Заглушка оплаты для MVP: заказ оформляется без оплаты (spec §8)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.payments.base import PaymentResult

if TYPE_CHECKING:
    from src.db.models import Order


class NoPaymentProvider:
    async def create_payment(self, order: Order) -> PaymentResult:
        return PaymentResult(paid=True, detail="MVP: оплата не требуется")
