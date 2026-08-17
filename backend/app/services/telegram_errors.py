"""Понятные сообщения об ошибках Telegram (Telethon) для UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.settings import settings


def humanize_telegram_error(raw: str | Exception | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()

    if "credentials not configured" in low or "telegram credentials not configured" in low:
        return (
            "Telegram-парсер не настроен. Откройте раздел «Telegram-парсер»: "
            "укажите api_id и api_hash, выполните вход по QR (или session string)."
        )
    if "connection to telegram failed" in low:
        return (
            "Не удалось подключиться к Telegram. Проверьте интернет/VPN и авторизацию "
            "в разделе «Telegram-парсер» (api_id, api_hash, вход по QR)."
        )
    if "session is not authorized" in low or ("not authorized" in low and "telegram" in low):
        return (
            "Сессия Telegram не авторизована. В разделе «Telegram-парсер» выполните вход по QR "
            "или обновите session string."
        )
    if "api_id" in low and "api_hash" in low and "обязательны" in low:
        return "Не заданы api_id и api_hash. Настройте их в разделе «Telegram-парсер»."
    if "floodwait" in low:
        return f"Telegram временно ограничил запросы ({s}). Повторите сбор позже."
    if "no user has" in low or "username not occupied" in low or "username invalid" in low:
        return f"Канал Telegram не найден. Проверьте @username канала: {s}"
    if "could not find the input entity" in low:
        return "Канал не найден в Telegram. Проверьте @username и что аккаунт парсера имеет доступ к каналу."

    return s


def telegram_readiness(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Готов ли Telegram-парсер к сбору.
    Возвращает (ready, сообщение_для_UI если не ready).
    """
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    session_string = (cfg.get("session_string") or "").strip()
    session_dir = settings.telegram_session_dir or "/data/tg"
    session_file = Path(session_dir) / "newsint_main.session"
    has_phone = bool(settings.telegram_phone)

    if not has_api:
        return False, "Не заданы api_id / api_hash. Настройте в разделе «Telegram-парсер»."

    if not session_string and not session_file.exists() and not has_phone:
        return False, (
            "Нет авторизованной сессии Telegram. Откройте «Telegram-парсер» и выполните вход по QR "
            "(или сохраните session string)."
        )

    return True, None
