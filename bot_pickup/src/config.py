"""Конфигурация бота. Источник — переменные окружения / `.env` (конституция §4, §6).

Секреты в коде не храним. Обязательные ключи валятся при старте (fail-fast).
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- v0-core: обязательные ---
    bot_token: str
    database_url: str
    redis_url: str
    staff_chat_id: int

    # --- каналы доставки и источник меню ---
    # ENABLED_SINKS — список через запятую, напр. "telegram" или "telegram,quickresto".
    enabled_sinks: Annotated[list[str], NoDecode] = ["telegram"]
    menu_source: str = "json"  # json | sheet | quickresto
    menu_path: str = "data/menu.json"
    pickup_time_enabled: bool = False  # флаг US-A4

    # --- prod ---
    webhook_url: str | None = None

    # --- Quick Resto открытое API (v1; для QuickRestoMenuSource) ---
    quickresto_base_url: str | None = None
    quickresto_api_login: str | None = None
    quickresto_api_password: str | None = None

    @field_validator("enabled_sinks", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Кешированный доступ к конфигу (читается один раз за процесс)."""
    return Settings()
