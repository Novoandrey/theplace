"""Юниты машины статусов (T036, §9)."""

from __future__ import annotations

import pytest

from src.db.models import OrderStatus
from src.orders.status import (
    InvalidTransition,
    assert_transition,
    can_transition,
    next_statuses,
)

S = OrderStatus


@pytest.mark.parametrize(
    "current,target",
    [
        (S.new, S.accepted),
        (S.new, S.rejected),
        (S.accepted, S.almost_ready),
        (S.accepted, S.rejected),
        (S.almost_ready, S.ready),
        (S.almost_ready, S.rejected),
        (S.ready, S.handed_out),
    ],
)
def test_valid_transitions(current, target):
    assert can_transition(current, target)
    assert_transition(current, target)  # не бросает


@pytest.mark.parametrize(
    "current,target",
    [
        (S.new, S.ready),  # перескок
        (S.new, S.handed_out),
        (S.accepted, S.handed_out),
        (S.almost_ready, S.accepted),  # назад
        (S.ready, S.rejected),  # после готовности не отклоняем
        (S.handed_out, S.accepted),  # терминальный
        (S.rejected, S.new),  # терминальный
    ],
)
def test_invalid_transitions(current, target):
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        assert_transition(current, target)


def test_next_statuses():
    assert next_statuses(S.new) == (S.accepted, S.rejected)
    assert next_statuses(S.ready) == (S.handed_out,)
    assert next_statuses(S.handed_out) == ()
    assert next_statuses(S.rejected) == ()
