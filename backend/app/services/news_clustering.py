"""Построение кластеров похожих новостей по simhash (Hamming distance)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import NewsItem, NewsItemCluster

log = logging.getLogger("services.news_clustering")


def _hamming64(a: int, b: int) -> int:
    return int((a ^ b).bit_count())


def rebuild_news_clusters(
    db: Session,
    *,
    days: int = 90,
    threshold: int = 3,
    max_items: int = 2000,
) -> dict[str, Any]:
    """
    Пересобрать таблицу кластеров по новостям с заполненным simhash64.
    Каждая новость попадает не более чем в один кластер; в кластер только пары с расхождением <= threshold.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    items = (
        db.query(NewsItem)
        .filter(NewsItem.published_at >= since)
        .filter(NewsItem.simhash64.isnot(None))
        .order_by(NewsItem.published_at.asc())
        .limit(max_items)
        .all()
    )
    if len(items) < 2:
        deleted = db.query(NewsItemCluster).delete(synchronize_session=False)
        db.commit()
        return {"deleted": deleted, "created": 0, "message": "мало новостей с simhash"}

    by_id = {n.id: n for n in items}
    pending: set[Any] = set(by_id.keys())
    cluster_groups: list[list[NewsItem]] = []

    while pending:
        sid = pending.pop()
        seed = by_id[sid]
        stack = [seed]
        group = [seed]
        while stack:
            cur = stack.pop()
            for oid in list(pending):
                o = by_id[oid]
                if cur.simhash64 is None or o.simhash64 is None:
                    continue
                if _hamming64(int(cur.simhash64), int(o.simhash64)) <= threshold:
                    pending.remove(oid)
                    group.append(o)
                    stack.append(o)
        if len(group) >= 2:
            group.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc))
            cluster_groups.append(group)

    deleted = db.query(NewsItemCluster).delete(synchronize_session=False)
    created = 0
    for grp in cluster_groups:
        primary = grp[0]
        related = [x.id for x in grp[1:]]
        db.add(
            NewsItemCluster(
                primary_item_id=primary.id,
                related_item_ids=related,
                similarity_threshold=threshold,
            )
        )
        created += 1
    db.commit()
    log.info("news clusters rebuilt", extra={"deleted": deleted, "created": created})
    return {"deleted": deleted, "created": created}
