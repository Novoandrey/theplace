"""Источник меню из локального JSON-файла (v0, зеркало реального меню The Place).

Особенности маппинга (plan §5): `option_groups` в файле — словарь по id (ключ → `OptionGroup.id`);
поля `price`/`price_delta` заданы в рублях и конвертируются в копейки; лишние верхнеуровневые
ключи игнорируются. Кеширование — в отдельном слое (`menu.cache`); здесь всегда читаем файл.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.menu.models import Category, Menu, MenuItem, OptionChoice, OptionGroup


def _rub_to_kopecks(value: float | int) -> int:
    return int(round(float(value) * 100))


class JsonFileMenuSource:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def get_menu(self, force_refresh: bool = False) -> Menu:  # noqa: ARG002 (файл читается всегда)
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return self._parse(raw)

    @staticmethod
    def _parse(raw: dict) -> Menu:
        categories = [Category(**c) for c in raw.get("categories", [])]
        groups: dict[str, OptionGroup] = {}
        for gid, g in raw.get("option_groups", {}).items():
            groups[gid] = OptionGroup(
                id=gid,
                title=g["title"],
                required=g.get("required", False),
                max_choices=g.get("max_choices", 1),
                choices=[
                    OptionChoice(
                        id=c["id"],
                        title=c["title"],
                        price_delta_kopecks=_rub_to_kopecks(c.get("price_delta", 0)),
                    )
                    for c in g.get("choices", [])
                ],
            )
        items = [
            MenuItem(
                id=it["id"],
                category=it["category"],
                title=it["title"],
                description=it.get("description", ""),
                serving=it.get("serving", ""),
                price_kopecks=_rub_to_kopecks(it["price"]),
                available=it.get("available", True),
                options=it.get("options", []),
                addons=it.get("addons", []),
            )
            for it in raw.get("items", [])
        ]
        addons_cfg = raw.get("addons", {})
        return Menu(
            currency=raw.get("currency", "RUB"),
            categories=categories,
            option_groups=groups,
            items=items,
            addon_category=addons_cfg.get("category"),
            addon_offer_categories=addons_cfg.get("offer_to_categories", []),
        )
