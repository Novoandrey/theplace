"""Async-движок SQLAlchemy."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config import get_settings


def make_engine() -> AsyncEngine:
    """Создаёт async-движок по DATABASE_URL (postgresql+asyncpg://...)."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
