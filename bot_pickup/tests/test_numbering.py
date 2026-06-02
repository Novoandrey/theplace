"""Юнит формата короткого номера заказа (§4.1). Атомарность счётчика проверена на живом PG."""

from __future__ import annotations

from src.orders.numbering import format_number


def test_format_pads_to_three():
    assert format_number(1) == "001"
    assert format_number(42) == "042"
    assert format_number(999) == "999"


def test_format_no_pad_over_999():
    assert format_number(1000) == "1000"
    assert format_number(1234) == "1234"
