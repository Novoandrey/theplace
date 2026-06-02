"""Кеш меню с TTL (конституция §8). `force_refresh=True` — для перепроверки стопа при
оформлении (FR-16), чтобы на живом источнике проверка читала свежие данные.
"""

from __future__ import annotations

import time

from src.menu.models import Menu
from src.menu.sources.base import MenuSource


class CachedMenuSource:
    def __init__(self, source: MenuSource, ttl_seconds: float = 60.0) -> None:
        self._source = source
        self._ttl = ttl_seconds
        self._cached: Menu | None = None
        self._fetched_at = 0.0

    async def get_menu(self, force_refresh: bool = False) -> Menu:
        now = time.monotonic()
        expired = (now - self._fetched_at) > self._ttl
        if force_refresh or self._cached is None or expired:
            self._cached = await self._source.get_menu(force_refresh=force_refresh)
            self._fetched_at = now
        return self._cached
