from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.domain import Competitor, Developer, Region


def _contains_any(text_lc: str, terms: list[str]) -> bool:
    for t in terms:
        t2 = (t or "").strip().lower()
        if not t2:
            continue
        if t2 in text_lc:
            return True
    return False


def tag_item(
    db: Session,
    *,
    text: str,
    source_region_ids: list[uuid.UUID] | None = None,
    source_competitor_id: uuid.UUID | None = None,
    source_developer_id: uuid.UUID | None = None,
) -> dict:
    """
    Rule-based tagging:
    - competitor / developer mentions by aliases (отдельные сущности)
    - region mapping by region keywords/aliases/subjects (+ source region tags)
    """
    text_lc = (text or "").lower()

    regions = db.query(Region).filter(Region.is_active.is_(True)).all()
    region_ids: set[uuid.UUID] = set(source_region_ids or [])
    for r in regions:
        terms = (r.federal_subjects or []) + (r.keywords or []) + (r.geographic_aliases or [])
        if _contains_any(text_lc, terms):
            region_ids.add(r.id)

    competitors = db.query(Competitor).filter(Competitor.is_active.is_(True)).all()
    competitor_mentions: set[uuid.UUID] = set()
    for c in competitors:
        terms = [c.name] + (c.aliases or []) + (c.tags or [])
        if _contains_any(text_lc, terms):
            competitor_mentions.add(c.id)

    developers = db.query(Developer).filter(Developer.is_active.is_(True)).all()
    developer_mentions: set[uuid.UUID] = set()
    for d in developers:
        terms = [d.name] + (d.aliases or []) + (d.tags or [])
        if _contains_any(text_lc, terms):
            developer_mentions.add(d.id)

    return {
        "region_ids": list(region_ids),
        "competitor_mentions": list(competitor_mentions),
        "developer_mentions": list(developer_mentions),
        "topic_tags": [],  # TODO: keyword sets
    }

