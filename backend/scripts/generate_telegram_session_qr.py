#!/usr/bin/env python3
"""
Generate Telethon StringSession via QR-код — БЕЗ кода по телефону/приложению.

Если код вообще не приходит — используйте этот скрипт. Отсканируйте QR в Telegram:
  Телефон: Настройки → Устройства → Подключить рабочий стол
  Desktop: Настройки → Устройства → Подключить устройство

Usage:
  1. TELEGRAM_API_ID, TELEGRAM_API_HASH в .env (TELEGRAM_PHONE не нужен!)
  2. python backend/scripts/generate_telegram_session_qr.py
  3. Отсканируйте QR в Telegram
  4. Скопируйте строку в TELEGRAM_SESSION_STRING
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(root / ".env")
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError


def _print_qr(url: str) -> None:
    """Print QR as ASCII or URL."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except ImportError:
        print("Установите: pip install qrcode")
        print("Или откройте в браузере:", url[:80] + "...")


async def main() -> None:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("Нужны TELEGRAM_API_ID и TELEGRAM_API_HASH в .env (TELEGRAM_PHONE не нужен)")
        sys.exit(1)

    api_id = int(api_id)
    client = TelegramClient(StringSession(), api_id, api_hash)

    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            session_str = client.session.save()
            _print_session(session_str, me)
            return

        print("\nОткройте Telegram → Настройки → Устройства → Подключить устройство")
        print("Отсканируйте QR-код:\n")

        qr = await client.qr_login()
        authorized = False

        while not authorized:
            _print_qr(qr.url)
            print("\nОжидание сканирования (QR обновляется каждые 60 сек)...")
            try:
                await qr.wait(timeout=60)
                authorized = True
            except asyncio.TimeoutError:
                print("Таймаут. Генерирую новый QR...")
                qr = await qr.recreate()
            except SessionPasswordNeededError:
                pw = input("Введите пароль 2FA: ").strip()
                await client.sign_in(password=pw)
                authorized = True

        me = await client.get_me()
        session_str = client.session.save()
        _print_session(session_str, me)
    finally:
        await client.disconnect()


def _print_session(session_str: str, me) -> None:
    print("\n" + "=" * 60)
    print("Session string (добавьте в .env как TELEGRAM_SESSION_STRING):")
    print("=" * 60)
    print(session_str)
    print("=" * 60)
    print(f"Авторизован: {getattr(me, 'username', None) or me.id}")


if __name__ == "__main__":
    asyncio.run(main())
