"""Настройки включаемых разделов отчёта (ИИ + HTML/PDF)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REGION_UNASSIGNED_LABEL = "Без региона"


@dataclass(frozen=True)
class ReportSectionSettings:
    include_news: bool
    include_indicators: bool
    include_regions: bool
    include_competitors: bool
    include_developers: bool
    include_general_news: bool
    include_clusters: bool
    include_region_unassigned: bool
    disabled_competitor_ids: frozenset[str]
    disabled_developer_ids: frozenset[str]
    disabled_region_ids: frozenset[str]


def parse_report_section_settings(cfg: dict[str, Any]) -> ReportSectionSettings:
    include_news = bool(cfg.get("include_news", True))
    return ReportSectionSettings(
        include_news=include_news,
        include_indicators=bool(cfg.get("include_indicators", True)),
        include_regions=bool(cfg.get("include_regions", True)),
        include_competitors=include_news and bool(cfg.get("include_competitors", True)),
        include_developers=include_news and bool(cfg.get("include_developers", True)),
        include_general_news=include_news and bool(cfg.get("include_general_news", True)),
        include_clusters=include_news and bool(cfg.get("include_clusters", True)),
        include_region_unassigned=bool(cfg.get("include_region_unassigned", True)),
        disabled_competitor_ids=_id_set(cfg.get("disabled_competitor_ids")),
        disabled_developer_ids=_id_set(cfg.get("disabled_developer_ids")),
        disabled_region_ids=_id_set(cfg.get("disabled_region_ids")),
    )


def _id_set(raw: Any) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(str(x) for x in raw if x)


def _name_to_id(entity_map: dict[str, str]) -> dict[str, str]:
    return {name: eid for eid, name in entity_map.items()}


def _entity_excluded(name: str, name_to_id: dict[str, str], disabled: frozenset[str]) -> bool:
    eid = name_to_id.get(name)
    if eid and eid in disabled:
        return True
    return name in disabled


def filter_competitor_groups(
    groups: dict[str, list],
    competitors_map: dict[str, str],
    settings: ReportSectionSettings,
) -> dict[str, list]:
    if not settings.include_competitors:
        return {}
    n2i = _name_to_id(competitors_map)
    return {
        name: items
        for name, items in groups.items()
        if not _entity_excluded(name, n2i, settings.disabled_competitor_ids)
    }


def filter_developer_groups(
    groups: dict[str, list],
    developers_map: dict[str, str],
    settings: ReportSectionSettings,
) -> dict[str, list]:
    if not settings.include_developers:
        return {}
    n2i = _name_to_id(developers_map)
    return {
        name: items
        for name, items in groups.items()
        if not _entity_excluded(name, n2i, settings.disabled_developer_ids)
    }


def filter_region_groups(
    groups: dict[str, list],
    region_map: dict[str, str],
    settings: ReportSectionSettings,
) -> dict[str, list]:
    if not settings.include_regions:
        return {}
    n2i = _name_to_id(region_map)
    out: dict[str, list] = {}
    for name, items in groups.items():
        if name == REGION_UNASSIGNED_LABEL:
            if settings.include_region_unassigned:
                out[name] = items
            continue
        if _entity_excluded(name, n2i, settings.disabled_region_ids):
            continue
        out[name] = items
    return out


def filter_processed_by_name(
    processed: dict[str, str] | None,
    processed_json: dict[str, Any] | None,
    *,
    competitors_map: dict[str, str] | None = None,
    developers_map: dict[str, str] | None = None,
    region_map: dict[str, str] | None = None,
    settings: ReportSectionSettings,
    kind: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    proc = dict(processed or {})
    proc_j = dict(processed_json or {})
    if kind == "competitor":
        if not settings.include_competitors:
            return {}, {}
        n2i = _name_to_id(competitors_map or {})
        disabled = settings.disabled_competitor_ids
    elif kind == "developer":
        if not settings.include_developers:
            return {}, {}
        n2i = _name_to_id(developers_map or {})
        disabled = settings.disabled_developer_ids
    elif kind == "region":
        if not settings.include_regions:
            return {}, {}
        n2i = _name_to_id(region_map or {})
        disabled = settings.disabled_region_ids
    else:
        return proc, proc_j

    keep = set()
    for name in set(proc) | set(proc_j):
        if kind == "region" and name == REGION_UNASSIGNED_LABEL:
            if settings.include_region_unassigned:
                keep.add(name)
            continue
        if not _entity_excluded(name, n2i, disabled):
            keep.add(name)

    return (
        {k: v for k, v in proc.items() if k in keep},
        {k: v for k, v in proc_j.items() if k in keep},
    )


def apply_section_filters_to_generated(
    db: Any,
    generated: dict[str, Any],
    settings: ReportSectionSettings,
) -> dict[str, Any]:
    """Убрать из payload отчёта разделы, отключённые в конфиге."""
    from app.models.domain import Competitor, Developer, Region

    g = dict(generated)
    comps = {str(c.id): c.name or str(c.id) for c in db.query(Competitor).filter(Competitor.is_active.is_(True)).all()}
    devs = {str(d.id): d.name or str(d.id) for d in db.query(Developer).filter(Developer.is_active.is_(True)).all()}
    regions = {str(r.id): r.name or str(r.id) for r in db.query(Region).filter(Region.is_active.is_(True)).all()}

    if not settings.include_indicators:
        g["processed_indicators"] = None
        g["processed_indicators_json"] = None
        g["indicator_telegram_sections"] = []
    if not settings.include_general_news:
        g["processed_news"] = None
        g["processed_news_json"] = None
    if not settings.include_clusters:
        g["processed_clusters"] = None
        g["processed_clusters_json"] = None

    pc, pcj = filter_processed_by_name(
        g.get("processed_competitors_by_name"),
        g.get("processed_competitors_by_name_json"),
        competitors_map=comps,
        settings=settings,
        kind="competitor",
    )
    g["processed_competitors_by_name"] = pc
    g["processed_competitors_by_name_json"] = pcj

    pd, pdj = filter_processed_by_name(
        g.get("processed_developers_by_name"),
        g.get("processed_developers_by_name_json"),
        developers_map=devs,
        settings=settings,
        kind="developer",
    )
    g["processed_developers_by_name"] = pd
    g["processed_developers_by_name_json"] = pdj

    pr, prj = filter_processed_by_name(
        g.get("processed_regions_by_name"),
        g.get("processed_regions_by_name_json"),
        region_map=regions,
        settings=settings,
        kind="region",
    )
    g["processed_regions_by_name"] = pr
    g["processed_regions_by_name_json"] = prj
    return g
