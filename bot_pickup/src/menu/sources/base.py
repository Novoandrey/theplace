"""Контракт источника меню (plan §5). Смена источника не меняет сценарии (конституция §3)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.menu.models import Menu


@runtime_checkable
class MenuSource(Protocol):
    async def get_menu(self, force_refresh: bool = False) -> Menu: ...
