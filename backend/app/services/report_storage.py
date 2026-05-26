"""Persist published HTML reports for public URLs."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.settings import settings

log = logging.getLogger("services.report_storage")


def _reports_dir() -> Path:
    d = Path(settings.storage_dir) / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_published_html(
    html: str,
    *,
    title: str,
    date_from: str,
    date_to: str,
    report_month: str | None = None,
) -> dict[str, Any]:
    report_id = uuid.uuid4().hex[:12]
    filename = f"{report_id}.html"
    path = _reports_dir() / filename
    path.write_text(html, encoding="utf-8")

    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "id": report_id,
        "filename": filename,
        "title": title,
        "date_from": date_from,
        "date_to": date_to,
        "report_month": report_month,
        "created_at": created_at,
        "public_path": f"/reports/{filename}",
    }
    (_reports_dir() / f"{report_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    removed = prune_published_reports()
    if removed:
        log.info("pruned old published reports", extra={"removed": removed})
    return meta


def prune_published_reports(
    *,
    keep_days: int | None = None,
    keep_count: int | None = None,
) -> int:
    """
    Удаляет старые опубликованные HTML+meta.
    keep_days: старше N дней удалить (0 = не проверять возраст).
    keep_count: оставить не более N последних (0 = без лимита по количеству).
    """
    keep_days = settings.reports_keep_days if keep_days is None else keep_days
    keep_count = settings.reports_keep_count if keep_count is None else keep_count

    d = _reports_dir()
    metas = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not metas:
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=keep_days) if keep_days > 0 else None
    removed = 0

    for idx, meta_path in enumerate(metas):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta_path.unlink(missing_ok=True)
            removed += 1
            continue

        if not isinstance(data, dict):
            meta_path.unlink(missing_ok=True)
            removed += 1
            continue

        too_old = False
        if cutoff is not None:
            created_raw = data.get("created_at") or ""
            try:
                created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                too_old = created_dt < cutoff
            except Exception:
                pass

        over_count = keep_count > 0 and idx >= keep_count
        if not (too_old or over_count):
            continue

        rid = data.get("id") or meta_path.stem
        html_name = data.get("filename") or f"{rid}.html"
        html_path = d / str(html_name)
        meta_path.unlink(missing_ok=True)
        html_path.unlink(missing_ok=True)
        removed += 1

    return removed


def delete_published_report(report_id: str) -> bool:
    """Удалить опубликованный HTML-отчёт и meta JSON. Возвращает False, если не найден."""
    rid = (report_id or "").strip()
    if not rid:
        return False
    d = _reports_dir()
    meta_path = d / f"{rid}.json"
    if not meta_path.is_file():
        return False
    html_name = f"{rid}.html"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("filename"):
            html_name = str(data["filename"])
    except Exception:
        pass
    meta_path.unlink(missing_ok=True)
    html_path = d / html_name
    if html_path.is_file():
        html_path.unlink()
    log.info("deleted published report", extra={"report_id": rid})
    return True


def list_published_reports(*, limit: int = 30) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for meta_path in sorted(_reports_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("id"):
                items.append(data)
        except Exception:
            continue
        if len(items) >= limit:
            break
    return items
