from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db import get_db
from app.models.auth import Role, User
from app.parsers.html_template_engine import extract_with_template
from app.schemas.templates import TemplateTestRequest, TemplateTestResult

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("/test", response_model=TemplateTestResult)
def test_template(
    payload: TemplateTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> TemplateTestResult:
    extracted = extract_with_template(str(payload.url), payload.template_json)
    body_text = extracted.body_text or ""
    preview = body_text[:800] if body_text else None
    return TemplateTestResult(
        url=extracted.url,
        title=extracted.title,
        author=extracted.author,
        published_at_raw=extracted.published_at_raw,
        published_at=extracted.published_at.isoformat() if extracted.published_at else None,
        body_text_preview=preview,
        body_text_length=len(body_text),
    )

