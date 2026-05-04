"""API for Telegram parser (MTProto/Telethon) configuration status and instructions."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_role
from app.core.settings import settings
from app.db import get_db
from app.models.auth import Role, User
from app.services.telegram_config import get_telegram_config, save_telegram_config
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import SessionPasswordNeededError as SessionPasswordNeededErrorRpc
from telethon.sessions import StringSession

router = APIRouter(prefix="/telegram-parser", tags=["telegram-parser"])

# In-memory storage for QR login flow (poll_id -> {status, session_string?, error?})
_qr_poll_storage: dict[str, dict[str, Any]] = {}


class TelegramParserStatusOut(BaseModel):
    credentials_configured: bool
    session_string_used: bool
    session_dir: str
    session_file_exists: bool
    session_authorized: bool | None
    verify_error: str | None = None
    config_source: str = "env"  # "db" or "env"


class TelegramConfigUpdateIn(BaseModel):
    api_id: int | None = Field(default=None, description="API ID from my.telegram.org")
    api_hash: str | None = Field(default=None, max_length=100)
    session_string: str | None = Field(default=None)


class TelegramConfigOut(BaseModel):
    api_id_set: bool
    api_hash_set: bool
    session_string_set: bool
    config_source: str


class QrStartIn(BaseModel):
    api_id: int
    api_hash: str


class QrStartOut(BaseModel):
    poll_id: str
    qr_url: str
    session_string: str | None = None  # Set when already authorized


class QrPollOut(BaseModel):
    status: str  # pending | done | error | timeout | 2fa_required
    session_string: str | None = None
    error: str | None = None


class Qr2faIn(BaseModel):
    poll_id: str
    password: str


async def _qr_wait_task(poll_id: str, client: TelegramClient, qr: Any) -> None:
    """Background task: wait for user to scan QR."""
    try:
        await qr.wait(timeout=120)
        session_str = client.session.save()
        _qr_poll_storage[poll_id] = {"status": "done", "session_string": session_str}
    except asyncio.TimeoutError:
        _qr_poll_storage[poll_id] = {"status": "timeout", "error": "QR истёк. Нажмите «Сгенерировать QR» снова."}
        await client.disconnect()
    except (SessionPasswordNeededError, SessionPasswordNeededErrorRpc):
        _qr_poll_storage[poll_id] = {"status": "2fa_required", "client": client}
    except Exception as e:
        err_msg = str(e).lower()
        if "password" in err_msg or "2fa" in err_msg or "two-step" in err_msg or "two step" in err_msg:
            _qr_poll_storage[poll_id] = {"status": "2fa_required", "client": client}
        else:
            _qr_poll_storage[poll_id] = {"status": "error", "error": str(e)}
            await client.disconnect()
    finally:
        data = _qr_poll_storage.get(poll_id)
        if data and data.get("status") != "2fa_required":
            try:
                await client.disconnect()
            except Exception:
                pass


async def _verify_session(cfg: dict[str, Any]) -> tuple[bool, str | None]:
    """Actually connect to Telegram and check if session is authorized."""
    api_id = cfg.get("api_id")
    api_hash = cfg.get("api_hash") or ""
    session_string = cfg.get("session_string") or ""
    if not api_id or not api_hash:
        return False, "api_id и api_hash обязательны"
    if session_string:
        session = StringSession(session_string)
    else:
        session = f"{settings.telegram_session_dir}/newsint_main"
    client = TelegramClient(
        session=session,
        api_id=api_id,
        api_hash=api_hash,
    )
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        return authorized, None
    except Exception as e:
        return False, str(e)
    finally:
        await client.disconnect()


def _config_source(db: Session) -> str:
    from app.models.config import TelegramConfig

    row = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if row and (row.api_id or row.api_hash or row.session_string):
        return "db"
    return "env"


@router.get("/config", response_model=TelegramConfigOut)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> TelegramConfigOut:
    """Get config status (masked, no values)."""
    cfg = get_telegram_config(db)
    return TelegramConfigOut(
        api_id_set=bool(cfg.get("api_id")),
        api_hash_set=bool(cfg.get("api_hash")),
        session_string_set=bool(cfg.get("session_string")),
        config_source=_config_source(db),
    )


@router.post("/qr-start", response_model=QrStartOut)
async def qr_start(
    payload: QrStartIn,
    user: User = Depends(require_role(Role.ADMIN)),
) -> QrStartOut:
    """Start QR login flow. Returns QR URL. Poll /qr-poll/{poll_id} for result."""
    client = TelegramClient(
        StringSession(),
        api_id=payload.api_id,
        api_hash=payload.api_hash.strip(),
    )
    await client.connect()
    if await client.is_user_authorized():
        session_str = client.session.save()
        await client.disconnect()
        return QrStartOut(poll_id="", qr_url="", session_string=session_str)
    qr = await client.qr_login()
    poll_id = str(uuid.uuid4())
    _qr_poll_storage[poll_id] = {"status": "pending"}
    asyncio.create_task(_qr_wait_task(poll_id, client, qr))
    return QrStartOut(poll_id=poll_id, qr_url=qr.url)


@router.get("/qr-poll/{poll_id}", response_model=QrPollOut)
def qr_poll(
    poll_id: str,
    user: User = Depends(require_role(Role.ADMIN)),
) -> QrPollOut:
    """Poll for QR scan result."""
    if poll_id not in _qr_poll_storage:
        raise HTTPException(status_code=404, detail="Poll not found")
    data = _qr_poll_storage[poll_id]
    return QrPollOut(
        status=data["status"],
        session_string=data.get("session_string"),
        error=data.get("error"),
    )


@router.post("/qr-2fa", response_model=QrPollOut)
async def qr_2fa(
    payload: Qr2faIn,
    user: User = Depends(require_role(Role.ADMIN)),
) -> QrPollOut:
    """Complete 2FA after QR scan. Call when qr-poll returns status 2fa_required."""
    poll_id = payload.poll_id
    if poll_id not in _qr_poll_storage:
        raise HTTPException(status_code=404, detail="Poll not found")
    data = _qr_poll_storage[poll_id]
    if data.get("status") != "2fa_required":
        raise HTTPException(status_code=400, detail="2FA not required")
    client = data.get("client")
    if not client:
        raise HTTPException(status_code=500, detail="Client lost")
    try:
        await client.sign_in(password=payload.password.strip())
        session_str = client.session.save()
        _qr_poll_storage[poll_id] = {"status": "done", "session_string": session_str}
        return QrPollOut(status="done", session_string=session_str)
    except Exception as e:
        _qr_poll_storage[poll_id] = {"status": "error", "error": str(e)}
        return QrPollOut(status="error", error=str(e))
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        if "client" in data:
            del data["client"]


@router.put("/config", response_model=TelegramConfigOut)
def update_config(
    payload: TelegramConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> TelegramConfigOut:
    """Save Telegram config (Admin only). Only updates fields present in request."""
    kwargs = payload.model_dump(exclude_unset=True)
    save_telegram_config(db, **kwargs)
    cfg = get_telegram_config(db)
    return TelegramConfigOut(
        api_id_set=bool(cfg.get("api_id")),
        api_hash_set=bool(cfg.get("api_hash")),
        session_string_set=bool(cfg.get("session_string")),
        config_source="db",
    )


@router.get("/status", response_model=TelegramParserStatusOut)
def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> TelegramParserStatusOut:
    """Returns Telegram parser configuration status."""
    cfg = get_telegram_config(db)
    session_string_used = bool(cfg.get("session_string"))
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    credentials_configured = has_api and (
        session_string_used or bool(settings.telegram_phone)
    )
    session_dir = settings.telegram_session_dir or "/data/tg"
    session_path = Path(session_dir) / "newsint_main.session"
    session_file_exists = session_path.exists()

    session_authorized: bool | None = None
    verify_error: str | None = None
    if credentials_configured and (session_string_used or session_file_exists):
        try:
            authorized, err = asyncio.run(_verify_session(cfg))
            session_authorized = authorized
            verify_error = err
        except Exception as e:
            session_authorized = False
            verify_error = str(e)

    return TelegramParserStatusOut(
        credentials_configured=credentials_configured,
        session_string_used=session_string_used,
        session_dir=session_dir,
        session_file_exists=session_file_exists,
        session_authorized=session_authorized,
        verify_error=verify_error,
        config_source=_config_source(db),
    )
