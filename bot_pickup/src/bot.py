"""Точка входа бота (plan §3, §12).

Dispatcher + RedisStorage (FSM наружу процесса — переживает рестарт, конституция §3).
Источник меню и список каналов доставки внедряются как workflow-данные диспетчера.
Dev: long-polling. Prod (webhook) — позже.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.config import Settings, get_settings
from src.db.engine import make_engine
from src.db.session import DbSessionMiddleware, make_sessionmaker
from src.handlers import cart, checkout, menu, staff, start
from src.menu.cache import CachedMenuSource
from src.menu.sources.base import MenuSource
from src.menu.sources.json import JsonFileMenuSource
from src.orders.sinks.base import OrderSink
from src.orders.sinks.telegram_staff import TelegramStaffChatSink

logger = logging.getLogger(__name__)


def build_menu_source(settings: Settings) -> MenuSource:
    if settings.menu_source == "json":
        return CachedMenuSource(JsonFileMenuSource(settings.menu_path))
    # sheet (v0.1) и quickresto (v1) — позже.
    raise ValueError(f"источник меню '{settings.menu_source}' пока не поддержан")


def build_sinks(settings: Settings, bot: Bot) -> list[OrderSink]:
    sinks: list[OrderSink] = []
    if "telegram" in settings.enabled_sinks:
        sinks.append(TelegramStaffChatSink(bot, settings.staff_chat_id))
    # v0-print добавит EscPosPrinterSink; v1.1 — QuickRestoTerminalSink.
    return sinks


def build_dispatcher(
    sessionmaker,
    storage,
    menu_source: MenuSource,
    order_sinks: list[OrderSink],
    staff_chat_id: int,
) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp["menu_source"] = menu_source
    dp["order_sinks"] = order_sinks
    dp["staff_chat_id"] = staff_chat_id
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(staff.router)
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    settings = get_settings()

    engine = make_engine()
    sessionmaker = make_sessionmaker(engine)
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(token=settings.bot_token)
    menu_source = build_menu_source(settings)
    order_sinks = build_sinks(settings, bot)
    dp = build_dispatcher(sessionmaker, storage, menu_source, order_sinks, settings.staff_chat_id)

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
