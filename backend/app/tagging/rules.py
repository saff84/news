from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.domain import Competitor, Region


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
) -> dict:
    """
    Rule-based tagging:
    - competitor mentions by aliases
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
    if source_competitor_id:
        competitor_mentions.add(source_competitor_id)
    for c in competitors:
        terms = [c.name] + (c.aliases or [])
        if _contains_any(text_lc, terms):
            competitor_mentions.add(c.id)

    return {
        "region_ids": list(region_ids),
        "competitor_mentions": list(competitor_mentions),
        "topic_tags": [],  # TODO: keyword sets
    }

