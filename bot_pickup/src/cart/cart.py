"""Корзина и расчёт суммы с учётом опций (plan §6).

Корзина сериализуется в FSM-хранилище (Redis). Цены считаются против `Menu`
на момент показа/оформления; снапшоты фиксируются при создании заказа.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from src.texts import ru

if TYPE_CHECKING:
    from src.menu.models import Menu

# Выборы-«по умолчанию» — не показываем в названии строки (чтобы не шуметь).
_SILENT_CHOICES = {"regular", "none"}


@dataclass
class CartLine:
    uid: int
    item_id: str
    options: dict[str, str]  # group_id -> choice_id
    qty: int
    addons: dict[str, int] = field(default_factory=dict)  # addon_item_id -> qty (FR-18)


@dataclass
class Cart:
    lines: list[CartLine] = field(default_factory=list)
    seq: int = 0

    @classmethod
    def from_state(cls, data: dict | None) -> Cart:
        data = data or {}
        lines = [
            CartLine(
                uid=d["uid"],
                item_id=d["item_id"],
                options=dict(d["options"]),
                qty=d["qty"],
                addons=dict(d.get("addons", {})),
            )
            for d in data.get("lines", [])
        ]
        default_seq = max((line.uid for line in lines), default=0)
        return cls(lines=lines, seq=data.get("seq", default_seq))

    def to_state(self) -> dict:
        return {"lines": [asdict(line) for line in self.lines], "seq": self.seq}

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @staticmethod
    def _sig(item_id: str, options: dict[str, str], addons: dict[str, int]) -> tuple:
        return (item_id, tuple(sorted(options.items())), tuple(sorted(addons.items())))

    def add(
        self,
        item_id: str,
        options: dict[str, str],
        qty: int = 1,
        addons: dict[str, int] | None = None,
    ) -> CartLine:
        addons = addons or {}
        sig = self._sig(item_id, options, addons)
        for line in self.lines:
            if self._sig(line.item_id, line.options, line.addons) == sig:
                line.qty += qty
                return line
        self.seq += 1
        line = CartLine(
            uid=self.seq, item_id=item_id, options=dict(options), qty=qty, addons=dict(addons)
        )
        self.lines.append(line)
        return line

    def set_qty(self, uid: int, qty: int) -> None:
        for line in self.lines:
            if line.uid == uid:
                if qty <= 0:
                    self.lines.remove(line)
                else:
                    line.qty = qty
                return

    def change_qty(self, uid: int, delta: int) -> None:
        for line in self.lines:
            if line.uid == uid:
                self.set_qty(uid, line.qty + delta)
                return

    def remove(self, uid: int) -> None:
        self.lines = [line for line in self.lines if line.uid != uid]


# --- расчёт и форматирование ---


def unit_kopecks(menu: Menu, item_id: str, options: dict[str, str]) -> int:
    item = menu.item(item_id)
    if item is None:
        return 0
    total = item.price_kopecks
    for gid, cid in options.items():
        group = menu.group(gid)
        if group is None:
            continue
        choice = next((c for c in group.choices if c.id == cid), None)
        if choice is not None:
            total += choice.price_delta_kopecks
    return total


def configured_unit_kopecks(
    menu: Menu, item_id: str, options: dict[str, str], addons: dict[str, int] | None = None
) -> int:
    """Цена единицы позиции: база + дельты опций + Σ (цена допа × кол-во)."""
    total = unit_kopecks(menu, item_id, options)
    for aid, q in (addons or {}).items():
        addon = menu.item(aid)
        if addon is not None and q > 0:
            total += addon.price_kopecks * q
    return total


def line_unit_kopecks(menu: Menu, line: CartLine) -> int:
    return configured_unit_kopecks(menu, line.item_id, line.options, line.addons)


def line_total_kopecks(menu: Menu, line: CartLine) -> int:
    return line_unit_kopecks(menu, line) * line.qty


def cart_total_kopecks(menu: Menu, cart: Cart) -> int:
    return sum(line_total_kopecks(menu, line) for line in cart.lines)


def line_title(menu: Menu, line: CartLine) -> str:
    item = menu.item(line.item_id)
    title = item.title if item else line.item_id
    extras: list[str] = []
    for gid, cid in line.options.items():
        if cid in _SILENT_CHOICES:
            continue
        group = menu.group(gid)
        choice = next((c for c in group.choices if c.id == cid), None) if group else None
        if choice is not None:
            extras.append(choice.title)
    base = f"{title} ({', '.join(extras)})" if extras else title
    return base + format_addons_inline(menu, line.addons)


def format_addons_inline(menu: Menu, addons: dict[str, int]) -> str:
    """' + Бекон, Яйцо ×2' для названия строки/билета; '' если допов нет."""
    parts: list[str] = []
    for aid, q in addons.items():
        addon = menu.item(aid)
        if addon is None or q <= 0:
            continue
        parts.append(addon.title if q == 1 else f"{addon.title} ×{q}")
    return f" + {', '.join(parts)}" if parts else ""


def addons_snapshot(menu: Menu, line: CartLine) -> list[dict]:
    snap: list[dict] = []
    for aid, q in line.addons.items():
        addon = menu.item(aid)
        if addon is None or q <= 0:
            continue
        snap.append(
            {
                "item_id": aid,
                "title": addon.title,
                "qty": q,
                "unit_price_kopecks": addon.price_kopecks,
                "total_kopecks": addon.price_kopecks * q,
            }
        )
    return snap


def options_snapshot(menu: Menu, line: CartLine) -> list[dict]:
    snap: list[dict] = []
    for gid, cid in line.options.items():
        group = menu.group(gid)
        if group is None:
            continue
        choice = next((c for c in group.choices if c.id == cid), None)
        if choice is None:
            continue
        snap.append(
            {
                "group": gid,
                "group_title": group.title,
                "choice": cid,
                "choice_title": choice.title,
                "delta_kopecks": choice.price_delta_kopecks,
            }
        )
    return snap


def format_kopecks(kopecks: int) -> str:
    if kopecks % 100 == 0:
        return f"{kopecks // 100} ₽"
    return f"{kopecks / 100:.2f} ₽"


def format_cart(menu: Menu, cart: Cart) -> str:
    if cart.is_empty:
        return ru.CART_EMPTY
    rows = [ru.CART_TITLE]
    for i, line in enumerate(cart.lines, 1):
        total = format_kopecks(line_total_kopecks(menu, line))
        rows.append(f"{i}. {line_title(menu, line)} · {line.qty} шт — {total}")
    rows.append("")
    rows.append(ru.CART_TOTAL.format(total=format_kopecks(cart_total_kopecks(menu, cart))))
    return "\n".join(rows)
