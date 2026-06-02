"""Внутренняя модель меню (plan §5). Схема повторяет `data/menu.json`.

Цены — в копейках (конвертация из рублей при загрузке в источнике). `option_groups` —
словарь по id группы.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OptionChoice(BaseModel):
    id: str
    title: str
    price_delta_kopecks: int = 0


class OptionGroup(BaseModel):
    id: str
    title: str
    required: bool = False
    max_choices: int = 1
    choices: list[OptionChoice] = Field(default_factory=list)


class Category(BaseModel):
    id: str
    title: str
    sort: int = 0


class MenuItem(BaseModel):
    id: str
    category: str
    title: str
    description: str = ""
    serving: str = ""
    price_kopecks: int
    available: bool = True
    options: list[str] = Field(default_factory=list)  # id групп опций


class Menu(BaseModel):
    currency: str = "RUB"
    categories: list[Category] = Field(default_factory=list)
    option_groups: dict[str, OptionGroup] = Field(default_factory=dict)
    items: list[MenuItem] = Field(default_factory=list)

    def categories_sorted(self) -> list[Category]:
        return sorted(self.categories, key=lambda c: c.sort)

    def items_in(self, category_id: str, *, available_only: bool = True) -> list[MenuItem]:
        return [
            it
            for it in self.items
            if it.category == category_id and (it.available or not available_only)
        ]

    def item(self, item_id: str) -> MenuItem | None:
        return next((it for it in self.items if it.id == item_id), None)

    def group(self, group_id: str) -> OptionGroup | None:
        return self.option_groups.get(group_id)
