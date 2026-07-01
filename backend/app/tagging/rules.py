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


def _geo_term_matches(text_lc: str, term: str) -> bool:
    """Гео-термины: подстрока + основа для склонений (Самара → в Самаре)."""
    t2 = (term or "").strip().lower()
    if not t2:
        return False
    if len(t2) <= _SHORT_TERM_MAX_LEN:
        pattern = rf"(?<![{_WORD_CHAR_CLASS}]){re.escape(t2)}(?![{_WORD_CHAR_CLASS}])"
        return bool(re.search(pattern, text_lc, flags=re.IGNORECASE))
    if t2 in text_lc:
        return True
    if len(t2) >= 4:
        stem = t2[:-1]
        pattern = rf"(?<![{_WORD_CHAR_CLASS}]){re.escape(stem)}"
        return bool(re.search(pattern, text_lc, flags=re.IGNORECASE))
    return False


def _contains_any_geo(text_lc: str, terms: list[str]) -> bool:
    for t in terms:
        if _geo_term_matches(text_lc, t):
            return True
    return False


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


def region_search_terms(region: Region) -> list[str]:
    return list(region.federal_subjects or []) + list(region.keywords or []) + list(region.geographic_aliases or [])


def match_region_ids_from_text(text: str, regions: list[Region]) -> list[uuid.UUID]:
    text_lc = text_for_entity_tagging(text)
    out: list[uuid.UUID] = []
    for r in regions:
        if _contains_any_geo(text_lc, region_search_terms(r)):
            out.append(r.id)
    return out


def resolve_region_ids(
    text: str,
    source_region_ids: list[uuid.UUID] | None,
    regions: list[Region],
) -> list[uuid.UUID]:
    """
    Регион из текста (субъекты/ключи/алиасы) имеет приоритет.
    Теги источника — только если в тексте нет ни одного гео-совпадения.
    """
    from_text = match_region_ids_from_text(text, regions)
    if from_text:
        return from_text
    return list(source_region_ids or [])


def effective_region_ids(
    item: object,
    regions_by_id: dict[uuid.UUID, Region],
    source_region_map: dict[uuid.UUID, list[uuid.UUID]],
) -> list[uuid.UUID]:
    """Актуальные region_ids для отчёта (пересчёт по тексту, без устаревших тегов источника)."""
    text = news_item_tagging_text(item)
    regions_list = list(regions_by_id.values())
    from_text = match_region_ids_from_text(text, regions_list)
    if from_text:
        return from_text
    source_id = getattr(item, "source_id", None)
    if source_id:
        return list(source_region_map.get(source_id) or [])
    return []


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
    region_ids_list = resolve_region_ids(text, source_region_ids, regions)

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
        "region_ids": region_ids_list,
        "competitor_mentions": list(competitor_mentions),
        "developer_mentions": list(developer_mentions),
        "topic_tags": [],  # TODO: keyword sets
    }
