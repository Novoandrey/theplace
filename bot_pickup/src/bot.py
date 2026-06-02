"""Точка входа бота (plan §3, §12).

Dispatcher + RedisStorage (FSM наружу процесса — переживает рестарт, конституция §3).
Dev: long-polling без публичного URL. Prod (webhook) — позже.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.config import get_settings
from src.db.engine import make_engine
from src.db.session import DbSessionMiddleware, make_sessionmaker
from src.handlers import start

logger = logging.getLogger(__name__)


def build_dispatcher(sessionmaker, storage) -> Dispatcher:
    """Собирает диспетчер: middleware + роутеры. Вынесено для тестируемости."""
    dp = Dispatcher(storage=storage)
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    dp.include_router(start.router)
    # Группы A–C добавят сюда: menu, cart, checkout, status, staff.
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    settings = get_settings()

    engine = make_engine()
    sessionmaker = make_sessionmaker(engine)
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(token=settings.bot_token)
    dp = build_dispatcher(sessionmaker, storage)

    logger.info("bot starting (long-polling)")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
