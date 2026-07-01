import uuid
from types import SimpleNamespace

from app.tagging.rules import (
    _pick_regions_from_scores,
    resolve_region_ids,
    score_region_matches,
)


def _region(name: str, terms: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        federal_subjects=[],
        keywords=terms,
        geographic_aliases=[],
        is_active=True,
    )


def test_samara_title_beats_vladivostok_in_body():
    volga = _region("Приволжский ФО", ["Самара", "Самарская область"])
    dfo = _region("Дальневосточный ФО", ["Владивосток", "Приморский край"])
    title = "Самаре не грозит дефицит новостроек"
    body = (
        "В красной зоне Крым, Красноярск и Владивосток. "
        "В Самаре срок реализации остатков 2,9 года."
    )
    scores = score_region_matches(title, body, [volga, dfo], [volga.id])
    picked = _pick_regions_from_scores(scores, [volga.id])
    assert picked == [volga.id]
    assert scores[volga.id] > scores[dfo.id]


def test_lnr_not_matched_by_generic_respublika():
    dnr = _region(
        "ДНР",
        ["Донецк", "ДНР", "Донецкая Народная Республика", "Республика"],
    )
    lnr = _region("ЛНР", ["Луганск", "ЛНР", "Луганская Народная Республика"])
    title = "Минстрой ЛНР меняет участки теплоснабжения в Луганске"
    body = "Программа модернизации в новых регионах республики продолжается."
    scores = score_region_matches(title, body, [dnr, lnr], [])
    picked = _pick_regions_from_scores(scores, [])
    assert picked == [lnr.id]
    assert dnr.id not in scores or scores.get(lnr.id, 0) > scores.get(dnr.id, 0)


def test_resolve_uses_title_parameter():
    volga = _region("Приволжский ФО", ["Самара"])
    dfo = _region("Дальневосточный ФО", ["Владивосток"])
    body = "Сравнение с Владивостоком и Казанью."
    title = "Самаре не грозит дефицит новостроек"
    result = resolve_region_ids(body, [volga.id], [volga, dfo], title=title)
    assert result == [volga.id]
