from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.models.domain import Competitor, Developer, Region

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_WORD_CHAR_CLASS = "a-z0-9а-яё"
_SHORT_TERM_MAX_LEN = 3

# Слишком общие слова — дают ложные регионы (ДНР с «Республика», сравнение городов в теле).
_GENERIC_GEO_TERMS = frozenset(
    {
        "республика",
        "народная",
        "национальная",
        "область",
        "край",
        "округ",
        "город",
        "район",
        "фо",
        "россия",
        "рф",
    }
)


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


def _usable_geo_term(term: str) -> bool:
    t = (term or "").strip().lower()
    if len(t) < 2:
        return False
    if t in _GENERIC_GEO_TERMS:
        return False
    return True


def _term_region_score(title_lc: str, body_lc: str, term: str) -> float:
    if not _usable_geo_term(term):
        return 0.0
    t = term.strip().lower()
    specificity = min(len(t), 16) / 16.0
    score = 0.0
    if title_lc and _geo_term_matches(title_lc, t):
        score += 4.0 + specificity * 2.0
    if body_lc:
        head = body_lc[:300]
        if _geo_term_matches(head, t):
            score += 1.2 + specificity
        elif _geo_term_matches(body_lc, t):
            score += 0.45 + specificity * 0.35
    return score


def _contains_any(text_lc: str, terms: list[str]) -> bool:
    for t in terms:
        if _term_matches(text_lc, t):
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


def news_item_title_and_body(item: object) -> tuple[str, str]:
    title = str(getattr(item, "title", "") or "").strip()
    body = " ".join(
        [
            str(getattr(item, "content_text", "") or ""),
            str(getattr(item, "snippet", "") or ""),
        ]
    ).strip()
    return title, body


def region_search_terms(region: Region) -> list[str]:
    return list(region.federal_subjects or []) + list(region.keywords or []) + list(region.geographic_aliases or [])


def score_region_matches(
    title: str,
    body: str,
    regions: list[Region],
    source_region_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, float]:
    title_lc = text_for_entity_tagging(title)
    body_lc = text_for_entity_tagging(body)
    scores: dict[uuid.UUID, float] = {}
    for r in regions:
        total = 0.0
        for term in region_search_terms(r):
            total += _term_region_score(title_lc, body_lc, term)
        if total > 0:
            scores[r.id] = total

    src = list(source_region_ids or [])
    if len(src) == 1 and src[0] in scores:
        scores[src[0]] += 3.0
    return scores


def _pick_regions_from_scores(
    scores: dict[uuid.UUID, float],
    source_region_ids: list[uuid.UUID] | None,
    *,
    max_regions: int = 1,
) -> list[uuid.UUID]:
    if not scores:
        return list(source_region_ids or [])
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top_id, top_score = ranked[0]
    if top_score < 1.0:
        return list(source_region_ids or [])

    picked = [top_id]
    if max_regions > 1 and len(ranked) > 1:
        second_id, second_score = ranked[1]
        if second_score >= top_score * 0.88:
            picked.append(second_id)
    return picked[:max_regions]


def resolve_region_ids(
    text: str,
    source_region_ids: list[uuid.UUID] | None,
    regions: list[Region],
    *,
    title: str | None = None,
    max_regions: int = 1,
) -> list[uuid.UUID]:
    """
    Один (редко два) регион на новость по скорингу:
    заголовок важнее тела, длинные термины важнее, тег источника — бонус.
    """
    t = (title or "").strip()
    body = text or ""
    if not t and body:
        t = body[:200]
    scores = score_region_matches(t, body, regions, source_region_ids)
    return _pick_regions_from_scores(scores, source_region_ids, max_regions=max_regions)


def effective_region_ids(
    item: object,
    regions_by_id: dict[uuid.UUID, Region],
    source_region_map: dict[uuid.UUID, list[uuid.UUID]],
) -> list[uuid.UUID]:
    title, body = news_item_title_and_body(item)
    regions_list = list(regions_by_id.values())
    source_id = getattr(item, "source_id", None)
    src_regions = list(source_region_map.get(source_id) or []) if source_id else []
    scores = score_region_matches(title, body, regions_list, src_regions)
    return _pick_regions_from_scores(scores, src_regions, max_regions=1)


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
    title: str | None = None,
    match_text: str | None = None,
    source_region_ids: list[uuid.UUID] | None = None,
    source_competitor_id: uuid.UUID | None = None,
    source_developer_id: uuid.UUID | None = None,
) -> dict:
    """
    Rule-based tagging:
    - competitor / developer mentions by aliases (отдельные сущности)
    - region mapping by region keywords/aliases/subjects (+ source region tags)
    """
    text_lc = text_for_entity_tagging(match_text if match_text is not None else text)

    regions = db.query(Region).filter(Region.is_active.is_(True)).all()
    region_ids_list = resolve_region_ids(text, source_region_ids, regions, title=title, max_regions=1)

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
