from __future__ import annotations

import asyncio

from telethon import TelegramClient

from app.core.settings import settings


async def _main_async() -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash or not settings.telegram_phone:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_PHONE in environment.")

    session_dir = settings.telegram_session_dir
    if not session_dir:
        raise SystemExit("Missing TELEGRAM_SESSION_DIR in environment.")

    phone = settings.telegram_phone
    session_name = f"{session_dir}/newsint_main"

    client = TelegramClient(session=session_name, api_id=settings.telegram_api_id, api_hash=settings.telegram_api_hash)
    try:
        # This is intentionally interactive (one-time setup).
        # Note: Since Feb 2023, Telegram sends codes ONLY to the app (not SMS) for third-party API.
        print("Sending login code... Check Telegram app (phone/Desktop/web) for the code — SMS is not sent.")
        await client.start(phone=phone)
        me = await client.get_me()
        print(f"Telegram session authorized for: {getattr(me, 'username', None) or getattr(me, 'id', None)}")
        print(f"Session saved to: {session_name}.session")
    finally:
        await client.disconnect()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

