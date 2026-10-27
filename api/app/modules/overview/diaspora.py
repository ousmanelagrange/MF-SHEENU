"""Où vit la famille : nombre de personnes vivantes par pays de résidence."""

from collections import Counter

from app.genealogy.graph import FamilyGraph


def by_country(graph: FamilyGraph) -> tuple[list[tuple[str, int]], int]:
    """Renvoie [(pays, nombre)] du plus peuplé au moins peuplé, et le nombre de personnes
    vivantes dont le pays n'est pas renseigné. Les écritures sont regroupées sans tenir
    compte de la casse ni des espaces (« cameroun », « Cameroun »)."""
    counts: Counter = Counter()
    spelling: dict[str, str] = {}
    unknown = 0
    for p in graph.persons.values():
        if not p.is_living:
            continue
        name = " ".join((p.country or "").split())
        if not name:
            unknown += 1
            continue
        key = name.casefold()
        spelling.setdefault(key, name)
        counts[key] += 1
    return [(spelling[k], n) for k, n in counts.most_common()], unknown
