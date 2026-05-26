"""API for report generation (AI processing + PDF)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.services.report_html_builder import build_report_html
from app.services.pdf_builder import build_report_pdf
from app.services.report_config import get_report_config
from app.services.report_generator import generate_report, get_report_data_for_pdf, _parse_report_month
from app.services.report_storage import list_published_reports, save_published_html

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportGenerateIn(BaseModel):
    date_from: date | None = Field(default=None, description="Начало периода")
    date_to: date | None = Field(default=None, description="Конец периода")
    date_range_days: int | None = Field(default=None, ge=1, le=365, description="Период в днях (если date_from/date_to не заданы)")
    report_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$", description="Месяц отчёта YYYY-MM (приоритет, строгая фильтрация по месяцу)")


class ReportGeneratePdfIn(ReportGenerateIn):
    """Параметры для PDF с опциональными выводами ИИ."""
    processed_indicators: str | None = Field(default=None, description="Выводы ИИ по индикаторам (под графиками)")
    processed_news: str | None = Field(default=None, description="Выводы ИИ по общим новостям")
    processed_competitors: str | None = Field(default=None, description="Устарело: только поимённые блоки")
    processed_regions: str | None = Field(default=None, description="Устарело: только поимённые блоки")
    processed_clusters: str | None = Field(default=None, description="Выводы ИИ по кластерам новостей")
    processed_news_json: dict[str, Any] | None = Field(default=None, description="Структурированная секция ИИ (JSON)")
    processed_indicators_json: dict[str, Any] | None = Field(default=None)
    processed_clusters_json: dict[str, Any] | None = Field(default=None)
    processed_competitors_by_name: dict[str, str] = Field(default_factory=dict)
    processed_developers_by_name: dict[str, str] = Field(default_factory=dict)
    processed_regions_by_name: dict[str, str] = Field(default_factory=dict)
    processed_competitors_by_name_json: dict[str, Any] = Field(default_factory=dict)
    processed_developers_by_name_json: dict[str, Any] = Field(default_factory=dict)
    processed_regions_by_name_json: dict[str, Any] = Field(default_factory=dict)


class ReportGenerateOut(BaseModel):
    report_config: dict
    period: dict
    ai_stats: dict = Field(default_factory=dict)
    processed_news: str | None
    processed_competitors: str | None
    processed_indicators: str | None
    processed_regions: str | None
    processed_clusters: str | None
    processed_news_json: dict[str, Any] | None = None
    processed_indicators_json: dict[str, Any] | None = None
    processed_clusters_json: dict[str, Any] | None = None
    processed_competitors_by_name: dict[str, str] = Field(default_factory=dict)
    processed_developers_by_name: dict[str, str] = Field(default_factory=dict)
    processed_regions_by_name: dict[str, str] = Field(default_factory=dict)
    processed_competitors_by_name_json: dict[str, Any] = Field(default_factory=dict)
    processed_developers_by_name_json: dict[str, Any] = Field(default_factory=dict)
    processed_regions_by_name_json: dict[str, Any] = Field(default_factory=dict)


class ReportPublishedOut(BaseModel):
    id: str
    filename: str
    public_path: str
    title: str
    date_from: str
    date_to: str
    report_month: str | None = None
    created_at: str


class ReportPublishedListOut(BaseModel):
    items: list[ReportPublishedOut]


def _resolve_report_period(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    date_range_days: int | None,
    report_month: str | None,
) -> tuple[date, date, date | None, dict]:
    from datetime import timedelta

    report_cfg = get_report_config(db)
    period_month_val: date | None = None
    rm = report_month or report_cfg.get("report_month")

    if rm:
        parsed = _parse_report_month(rm)
        if parsed:
            date_from, date_to, period_month_val = parsed

    if date_from is None or date_to is None:
        days = date_range_days or report_cfg.get("date_range_days", 30)
        date_to = date_to or date.today()
        date_from = date_from or (date_to - timedelta(days=days))

    return date_from, date_to, period_month_val, report_cfg


def _build_html_report_data(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    period_month_val: date | None,
    report_cfg: dict,
    report_month: str | None = None,
    generated: dict | None = None,
) -> dict:
    if generated is None:
        generated = generate_report(
            db,
            date_from=date_from,
            date_to=date_to,
            report_month=report_month,
        )
    data = get_report_data_for_pdf(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month=period_month_val,
        include_news=report_cfg.get("include_news", True),
        include_indicators=report_cfg.get("include_indicators", True),
        include_regions=report_cfg.get("include_regions", True),
    )
    data["report_config"] = generated["report_config"]
    data["processed_indicators"] = generated.get("processed_indicators")
    data["processed_news"] = generated.get("processed_news")
    data["processed_competitors"] = generated.get("processed_competitors")
    data["processed_regions"] = generated.get("processed_regions")
    data["processed_clusters"] = generated.get("processed_clusters")
    data["processed_news_json"] = generated.get("processed_news_json")
    data["processed_indicators_json"] = generated.get("processed_indicators_json")
    data["processed_clusters_json"] = generated.get("processed_clusters_json")
    data["processed_competitors_by_name"] = generated.get("processed_competitors_by_name") or {}
    data["processed_developers_by_name"] = generated.get("processed_developers_by_name") or {}
    data["processed_regions_by_name"] = generated.get("processed_regions_by_name") or {}
    data["processed_competitors_by_name_json"] = generated.get("processed_competitors_by_name_json") or {}
    data["processed_developers_by_name_json"] = generated.get("processed_developers_by_name_json") or {}
    data["processed_regions_by_name_json"] = generated.get("processed_regions_by_name_json") or {}
    return data


@router.post("/generate", response_model=ReportGenerateOut)
def generate(
    payload: ReportGenerateIn | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> ReportGenerateOut:
    """
    Сгенерировать отчёт: собрать данные за период, обработать ИИ по каждому разделу,
    вернуть обработанные данные для PDF.
    В PDF идут только данные, прошедшие через ИИ (или сырые, если промпт не задан).
    """
    p = payload or ReportGenerateIn()
    result = generate_report(
        db,
        date_from=p.date_from,
        date_to=p.date_to,
        date_range_days=p.date_range_days,
        report_month=p.report_month,
    )
    return ReportGenerateOut(**result)


@router.post("/generate-pdf")
def generate_pdf(
    payload: ReportGeneratePdfIn | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> Response:
    """
    Сгенерировать PDF. Графики индикаторов, новости по регионам и каналам.
    Если переданы processed_* — выводы ИИ добавляются под соответствующими разделами.
    """
    from datetime import timedelta

    from app.services.report_generator import _parse_report_month

    p = payload or ReportGeneratePdfIn()
    report_cfg = get_report_config(db)
    period_month_val = None
    date_from = p.date_from
    date_to = p.date_to

    if p.report_month:
        parsed = _parse_report_month(p.report_month)
        if parsed:
            date_from, date_to, period_month_val = parsed

    if date_from is None or date_to is None:
        days = p.date_range_days or report_cfg.get("date_range_days", 30)
        date_to = date_to or date.today()
        date_from = date_from or (date_to - timedelta(days=days))

    data = get_report_data_for_pdf(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month=period_month_val,
        include_news=report_cfg.get("include_news", True),
        include_indicators=report_cfg.get("include_indicators", True),
        include_regions=report_cfg.get("include_regions", True),
    )
    data["report_config"] = {
        "title": report_cfg.get("title", "Аналитический отчёт"),
        "subtitle": report_cfg.get("subtitle", ""),
        "company_name": report_cfg.get("company_name", ""),
        "company_address": report_cfg.get("company_address", ""),
        "footer_text": report_cfg.get("footer_text", ""),
    }
    data["processed_indicators"] = p.processed_indicators
    data["processed_news"] = p.processed_news
    data["processed_competitors"] = p.processed_competitors
    data["processed_regions"] = p.processed_regions
    data["processed_clusters"] = p.processed_clusters
    data["processed_news_json"] = p.processed_news_json
    data["processed_indicators_json"] = p.processed_indicators_json
    data["processed_clusters_json"] = p.processed_clusters_json
    data["processed_competitors_by_name"] = p.processed_competitors_by_name or {}
    data["processed_developers_by_name"] = p.processed_developers_by_name or {}
    data["processed_regions_by_name"] = p.processed_regions_by_name or {}
    data["processed_competitors_by_name_json"] = p.processed_competitors_by_name_json or {}
    data["processed_developers_by_name_json"] = p.processed_developers_by_name_json or {}
    data["processed_regions_by_name_json"] = p.processed_regions_by_name_json or {}

    pdf_bytes = build_report_pdf(**data)
    period = data["period"]
    filename = f"report_{period.get('date_from', '')}_{period.get('date_to', '')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-html")
def generate_html(
    payload: ReportGenerateIn | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> Response:
    """
    Сгенерировать современный HTML-отчёт:
    интерактивные графики и саммари по каждому конкуренту/региону.
    """
    p = payload or ReportGenerateIn()
    date_from, date_to, period_month_val, report_cfg = _resolve_report_period(
        db,
        date_from=p.date_from,
        date_to=p.date_to,
        date_range_days=p.date_range_days,
        report_month=p.report_month,
    )
    data = _build_html_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month_val=period_month_val,
        report_cfg=report_cfg,
        report_month=p.report_month,
    )
    html = build_report_html(**data)
    period = data["period"]
    filename = f"report_{period.get('date_from', '')}_{period.get('date_to', '')}.html"
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/publish-html", response_model=ReportPublishedOut)
def publish_html(
    payload: ReportGenerateIn | None = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
) -> ReportPublishedOut:
    """
    Сгенерировать HTML-отчёт, сохранить на диск и вернуть публичный путь /reports/{id}.html.
    """
    p = payload or ReportGenerateIn()
    date_from, date_to, period_month_val, report_cfg = _resolve_report_period(
        db,
        date_from=p.date_from,
        date_to=p.date_to,
        date_range_days=p.date_range_days,
        report_month=p.report_month,
    )
    data = _build_html_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        period_month_val=period_month_val,
        report_cfg=report_cfg,
        report_month=p.report_month,
    )
    html = build_report_html(**data)
    meta = save_published_html(
        html,
        title=report_cfg.get("title", "Аналитический отчёт"),
        date_from=str(date_from),
        date_to=str(date_to),
        report_month=p.report_month,
    )
    return ReportPublishedOut(**meta)


@router.get("/published", response_model=ReportPublishedListOut)
def list_published(
    limit: int = 30,
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)),
) -> ReportPublishedListOut:
    """Список опубликованных HTML-отчётов (последние сверху)."""
    items = [ReportPublishedOut(**m) for m in list_published_reports(limit=limit)]
    return ReportPublishedListOut(items=items)
