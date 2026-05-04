#!/usr/bin/env python3
"""
Generate Telethon StringSession for NewsInt Telegram parser.

Run this script on a machine where you can receive the Telegram code
(e.g. your PC with Telegram Desktop). No need for tg-auth in Docker.

Usage:
  1. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env
  2. From project root: python backend/scripts/generate_telegram_session_string.py
     Or from backend: python scripts/generate_telegram_session_string.py
  3. Enter the code from Telegram (check Telegram app first, then SMS)
  4. Copy the printed string to TELEGRAM_SESSION_STRING in .env
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Load .env from project root
try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(root / ".env")
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not api_id or not api_hash or not phone:
        print("Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in environment.")
        sys.exit(1)

    api_id = int(api_id)
    client = TelegramClient(StringSession(), api_id, api_hash)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            # start() handles code + 2FA password interactively
            await client.start(phone=phone)
        me = await client.get_me()
        session_str = client.session.save()
        print("\n" + "=" * 60)
        print("Session string (add to .env as TELEGRAM_SESSION_STRING):")
        print("=" * 60)
        print(session_str)
        print("=" * 60)
        print(f"Authorized for: {getattr(me, 'username', None) or me.id}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
