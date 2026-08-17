"""API: парсинг TG-каналов конкурентов и AI-саммари."""

from __future__ import annotations

import datetime as dt
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.models.domain import Competitor, CompetitorTelegramPost, CompetitorTelegramProfile, CompetitorTelegramSummary
from app.services.competitor_summary_service import generate_competitor_summary, purge_competitor_posts
from app.services.report_section_render import render_section_inner_html
from app.services.telegram_config import get_telegram_config
from app.services.telegram_errors import humanize_telegram_error, telegram_readiness
from app.workers.jobs import competitor_tg_collect_job
from app.workers.queue import get_queue

router = APIRouter(prefix="/competitor-telegram", tags=["competitor-telegram"])


def _default_until_date() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=730)).date()


class ProfileOut(BaseModel):
    id: str
    competitor_id: str
    competitor_name: str
    tg_channel_username: str
    include_keywords: list[str]
    exclude_keywords: list[str]
    match_whole_words: bool
    backfill_until_date: str | None
    last_message_id: int
    backfill_complete: bool
    last_fetch_at: str | None
    last_error: str | None
    is_active: bool
    posts_count: int
    summary_status: str | None
    summary_html_path: str | None
    created_at: str
    updated_at: str


class ProfileCreateIn(BaseModel):
    competitor_id: uuid.UUID
    tg_channel_username: str = Field(min_length=1, max_length=128)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    match_whole_words: bool = False
    backfill_until_date: str | None = Field(
        default=None,
        description="YYYY-MM-DD — собирать посты начиная с этой даты (по умолчанию 24 мес. назад)",
    )
    is_active: bool = True


class ProfileUpdateIn(BaseModel):
    tg_channel_username: str | None = Field(default=None, max_length=128)
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    match_whole_words: bool | None = None
    backfill_until_date: str | None = None
    is_active: bool | None = None


class PostOut(BaseModel):
    id: str
    message_id: int
    post_url: str
    text: str | None
    published_at: str | None
    created_at: str


class SummaryOut(BaseModel):
    id: str
    profile_id: str
    status: str
    summary_text: str | None
    summary_json: dict
    summary_html: str | None = None
    posts_count: int
    period_from: str | None
    period_to: str | None
    html_path: str | None
    approved_at: str | None
    created_at: str
    updated_at: str


def _summary_render_payload(summary_json: dict | None) -> dict:
    raw = summary_json or {}
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}


def _summary_to_out(summary: CompetitorTelegramSummary) -> SummaryOut:
    payload = _summary_render_payload(summary.summary_json)
    summary_html = render_section_inner_html(text=summary.summary_text, payload=payload or None)
    if summary_html.startswith("<div"):
        m = re.search(r"<div[^>]*>(.*)</div>\s*$", summary_html, re.DOTALL)
        summary_html = m.group(1) if m else summary_html
    return SummaryOut(
        id=str(summary.id),
        profile_id=str(summary.profile_id),
        status=summary.status,
        summary_text=summary.summary_text,
        summary_json=summary.summary_json or {},
        summary_html=summary_html or None,
        posts_count=summary.posts_count,
        period_from=summary.period_from.isoformat() if summary.period_from else None,
        period_to=summary.period_to.isoformat() if summary.period_to else None,
        html_path=summary.html_path,
        approved_at=summary.approved_at.isoformat() if summary.approved_at else None,
        created_at=summary.created_at.isoformat() if summary.created_at else "",
        updated_at=summary.updated_at.isoformat() if summary.updated_at else "",
    )


def _parse_date(raw: str | None) -> dt.date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return dt.date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _latest_summary(db: Session, profile_id: uuid.UUID) -> CompetitorTelegramSummary | None:
    return (
        db.query(CompetitorTelegramSummary)
        .filter(CompetitorTelegramSummary.profile_id == profile_id)
        .order_by(CompetitorTelegramSummary.created_at.desc())
        .first()
    )


def _profile_out(db: Session, profile: CompetitorTelegramProfile) -> ProfileOut:
    competitor = db.get(Competitor, profile.competitor_id)
    posts_count = db.query(CompetitorTelegramPost).filter(CompetitorTelegramPost.profile_id == profile.id).count()
    summary = _latest_summary(db, profile.id)
    return ProfileOut(
        id=str(profile.id),
        competitor_id=str(profile.competitor_id),
        competitor_name=competitor.name if competitor else str(profile.competitor_id),
        tg_channel_username=profile.tg_channel_username,
        include_keywords=list(profile.include_keywords or []),
        exclude_keywords=list(profile.exclude_keywords or []),
        match_whole_words=bool(profile.match_whole_words),
        backfill_until_date=profile.backfill_until_date.isoformat() if profile.backfill_until_date else None,
        last_message_id=int(profile.last_message_id or 0),
        backfill_complete=bool(profile.backfill_complete),
        last_fetch_at=profile.last_fetch_at.isoformat() if profile.last_fetch_at else None,
        last_error=humanize_telegram_error(profile.last_error),
        is_active=bool(profile.is_active),
        posts_count=posts_count,
        summary_status=summary.status if summary else None,
        summary_html_path=summary.html_path if summary else None,
        created_at=profile.created_at.isoformat() if profile.created_at else "",
        updated_at=profile.updated_at.isoformat() if profile.updated_at else "",
    )


@router.get("/profiles")
def list_profiles(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> dict:
    rows = db.query(CompetitorTelegramProfile).order_by(CompetitorTelegramProfile.created_at.desc()).all()
    return {"items": [_profile_out(db, r) for r in rows]}


class TelegramStatusOut(BaseModel):
    ready: bool
    message: str | None
    credentials_configured: bool
    session_configured: bool


@router.get("/telegram-status", response_model=TelegramStatusOut)
def telegram_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> TelegramStatusOut:
    cfg = get_telegram_config(db)
    ready, message = telegram_readiness(cfg)
    has_api = bool(cfg.get("api_id") and cfg.get("api_hash"))
    has_session = bool((cfg.get("session_string") or "").strip())
    from pathlib import Path

    from app.core.settings import settings

    session_file = Path(settings.telegram_session_dir or "/data/tg") / "newsint_main.session"
    session_configured = has_session or session_file.exists() or bool(settings.telegram_phone)
    return TelegramStatusOut(
        ready=ready,
        message=message,
        credentials_configured=has_api,
        session_configured=session_configured,
    )


@router.post("/profiles", response_model=ProfileOut, status_code=201)
def create_profile(
    payload: ProfileCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ProfileOut:
    competitor = db.get(Competitor, payload.competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    existing = (
        db.query(CompetitorTelegramProfile)
        .filter(CompetitorTelegramProfile.competitor_id == payload.competitor_id)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Профиль для этого конкурента уже существует")
    username = payload.tg_channel_username.strip().lstrip("@")
    until = _parse_date(payload.backfill_until_date) or _default_until_date()
    profile = CompetitorTelegramProfile(
        competitor_id=payload.competitor_id,
        tg_channel_username=username,
        include_keywords=[k.strip() for k in payload.include_keywords if k.strip()],
        exclude_keywords=[k.strip() for k in payload.exclude_keywords if k.strip()],
        match_whole_words=payload.match_whole_words,
        backfill_until_date=until,
        is_active=payload.is_active,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _profile_out(db, profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: uuid.UUID,
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ProfileOut:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    data = payload.model_dump(exclude_unset=True)
    if "tg_channel_username" in data and data["tg_channel_username"] is not None:
        profile.tg_channel_username = data["tg_channel_username"].strip().lstrip("@")
    if "include_keywords" in data and data["include_keywords"] is not None:
        profile.include_keywords = [k.strip() for k in data["include_keywords"] if k.strip()]
    if "exclude_keywords" in data and data["exclude_keywords"] is not None:
        profile.exclude_keywords = [k.strip() for k in data["exclude_keywords"] if k.strip()]
    if "match_whole_words" in data and data["match_whole_words"] is not None:
        profile.match_whole_words = data["match_whole_words"]
    if "backfill_until_date" in data:
        profile.backfill_until_date = _parse_date(data["backfill_until_date"]) or profile.backfill_until_date
    if "is_active" in data and data["is_active"] is not None:
        profile.is_active = data["is_active"]
    db.commit()
    db.refresh(profile)
    return _profile_out(db, profile)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()


@router.get("/profiles/{profile_id}/posts")
def list_posts(
    profile_id: uuid.UUID,
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> dict:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    q = db.query(CompetitorTelegramPost).filter(CompetitorTelegramPost.profile_id == profile_id)
    total = q.count()
    rows = (
        q.order_by(CompetitorTelegramPost.published_at.desc().nullslast(), CompetitorTelegramPost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        PostOut(
            id=str(r.id),
            message_id=int(r.message_id),
            post_url=r.post_url,
            text=r.text,
            published_at=r.published_at.isoformat() if r.published_at else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return {"items": items, "total": total}


@router.post("/profiles/{profile_id}/collect")
def collect_posts(
    profile_id: uuid.UUID,
    reset_history: bool = Query(False, description="Сбросить курсор и собрать историю заново"),
    sync: bool = Query(False, description="Синхронный запуск (без очереди, один батч)"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    cfg = get_telegram_config(db)
    ready, tg_msg = telegram_readiness(cfg)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=tg_msg or "Telegram-парсер не готов. Настройте раздел «Telegram-парсер».",
        )
    if sync:
        from app.parsers.competitor_telegram_ingestor import ingest_competitor_telegram

        try:
            return ingest_competitor_telegram(db, profile, reset_history=reset_history)
        except Exception as e:
            msg = humanize_telegram_error(e) or str(e)
            raise HTTPException(status_code=502, detail=f"Ошибка сбора TG: {msg}")
    job = get_queue("default").enqueue(
        competitor_tg_collect_job,
        str(profile_id),
        reset_history,
        job_timeout=900,
    )
    return {"status": "queued", "job_id": job.id, "profile_id": str(profile_id)}


@router.post("/profiles/{profile_id}/summarize", response_model=SummaryOut)
def summarize_profile(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> SummaryOut:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        summary = generate_competitor_summary(db, profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка ИИ: {e!s}")
    return _summary_to_out(summary)


@router.get("/profiles/{profile_id}/summary", response_model=SummaryOut | None)
def get_summary(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> SummaryOut | None:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    summary = _latest_summary(db, profile_id)
    if not summary:
        return None
    return _summary_to_out(summary)


@router.post("/profiles/{profile_id}/approve-summary")
def approve_summary(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    summary = _latest_summary(db, profile_id)
    if not summary or summary.status != "ready":
        raise HTTPException(status_code=400, detail="Нет готового саммари для одобрения")
    summary.status = "approved"
    summary.approved_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return {"status": "approved", "summary_id": str(summary.id)}


@router.post("/profiles/{profile_id}/purge-posts")
def purge_posts(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict:
    profile = db.get(CompetitorTelegramProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    summary = _latest_summary(db, profile_id)
    if not summary or summary.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Сначала одобрите саммари (approve-summary), затем удаляйте посты",
        )
    return purge_competitor_posts(db, profile)
