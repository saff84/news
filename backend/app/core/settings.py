from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_str_none(v: object) -> object:
    """Coerce empty string from env to None for optional fields."""
    if v == "" or v is None:
        return None
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str
    redis_url: str
    secret_key: str

    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 14

    cors_origins: str = "http://localhost:5173"

    storage_dir: str = "/data/storage"
    telegram_session_dir: str = "/data/tg"

    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_phone: str | None = None
    telegram_session_string: str | None = None  # Alternative to tg-auth: use pre-generated StringSession
    max_api_base: str = "https://platform-api.max.ru"
    max_bot_token: str | None = None
    vk_api_base: str = "https://api.vk.com/method"
    vk_api_version: str = "5.199"
    vk_access_token: str | None = None

    enable_llm: bool = False

    @field_validator("telegram_api_id", "telegram_session_string", "max_bot_token", "vk_access_token", mode="before")
    @classmethod
    def _coerce_empty_to_none(cls, v: object) -> object:
        return _empty_str_none(v)


settings = Settings()
