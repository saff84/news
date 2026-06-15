from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.models.domain import Competitor, Developer, Region

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Латиница + кириллица — для границ «слова» при коротких алиасах (spl, цб, …)
_WORD_CHAR_CLASS = "a-z0-9а-яё"
_SHORT_TERM_MAX_LEN = 3


def text_for_entity_tagging(text: str) -> str:
    """Текст для поиска алиасов: без URL (в slug часто ложные вхождения, напр. spl в ekspluataciyu)."""
    return _URL_RE.sub(" ", text or "").lower()


def _term_matches(text_lc: str, term: str) -> bool:
    t2 = (term or "").strip().lower()
    if not t2:
        return False
    if len(t2) <= _SHORT_TERM_MAX_LEN:
        pattern = rf"(?<![{_WORD_CHAR_CLASS}]){re.escape(t2)}(?![{_WORD_CHAR_CLASS}])"
        return bool(re.search(pattern, text_lc, flags=re.IGNORECASE))
    return t2 in text_lc


def _contains_any(text_lc: str, terms: list[str]) -> bool:
    for t in terms:
        if _term_matches(text_lc, t):
            return True
    return False


def entity_search_terms(entity: Competitor | Developer) -> list[str]:
    return [entity.name] + (entity.aliases or []) + (entity.tags or [])


def terms_match_text(text: str, terms: list[str]) -> bool:
    return _contains_any(text_for_entity_tagging(text), terms)


def news_item_tagging_text(item: object) -> str:
    return " ".join(
        [
            str(getattr(item, "title", "") or ""),
            str(getattr(item, "content_text", "") or ""),
            str(getattr(item, "snippet", "") or ""),
        ]
    )


def filter_competitor_mentions(item: object, competitors_by_id: dict[uuid.UUID, Competitor]) -> list[uuid.UUID]:
    text = news_item_tagging_text(item)
    out: list[uuid.UUID] = []
    for cid in getattr(item, "competitor_mentions", None) or []:
        c = competitors_by_id.get(cid)
        if c and terms_match_text(text, entity_search_terms(c)):
            out.append(cid)
    return out


def filter_developer_mentions(item: object, developers_by_id: dict[uuid.UUID, Developer]) -> list[uuid.UUID]:
    text = news_item_tagging_text(item)
    out: list[uuid.UUID] = []
    for did in getattr(item, "developer_mentions", None) or []:
        d = developers_by_id.get(did)
        if d and terms_match_text(text, entity_search_terms(d)):
            out.append(did)
    return out


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
    text_lc = text_for_entity_tagging(text)

    regions = db.query(Region).filter(Region.is_active.is_(True)).all()
    region_ids: set[uuid.UUID] = set(source_region_ids or [])
    for r in regions:
        terms = (r.federal_subjects or []) + (r.keywords or []) + (r.geographic_aliases or [])
        if _contains_any(text_lc, terms):
            region_ids.add(r.id)

    competitors = db.query(Competitor).filter(Competitor.is_active.is_(True)).all()
    competitor_mentions: set[uuid.UUID] = set()
    for c in competitors:
        if _contains_any(text_lc, entity_search_terms(c)):
            competitor_mentions.add(c.id)

    developers = db.query(Developer).filter(Developer.is_active.is_(True)).all()
    developer_mentions: set[uuid.UUID] = set()
    for d in developers:
        if _contains_any(text_lc, entity_search_terms(d)):
            developer_mentions.add(d.id)

    return {
        "region_ids": list(region_ids),
        "competitor_mentions": list(competitor_mentions),
        "developer_mentions": list(developer_mentions),
        "topic_tags": [],  # TODO: keyword sets
    }
