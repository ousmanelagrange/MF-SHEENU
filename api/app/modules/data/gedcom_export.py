"""Export GEDCOM 5.5.1 — docs/03-conception-detaillee.md §2.7."""

from datetime import date
from uuid import UUID

from app.genealogy.graph import FamilyGraph

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _date(d: date | None, year: int | None) -> str | None:
    if d:
        return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"
    if year:
        return str(year)
    return None


def _clean(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ").strip()


def export_gedcom(graph: FamilyGraph, family_name: str, include_living_dates: bool) -> str:
    ids: dict[UUID, str] = {pid: f"@I{i}@" for i, pid in enumerate(graph.persons, start=1)}
    lines = [
        "0 HEAD",
        "1 SOUR SHEENU",
        "2 NAME Sheenu",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
        f"1 NOTE Famille {_clean(family_name)}",
    ]

    # Familles GEDCOM : une par union, plus une par parent seul ayant des enfants hors union.
    fams: list[dict] = []
    fam_index: dict[frozenset, dict] = {}
    for u in graph.unions:
        if u.person_a_id not in ids or u.person_b_id not in ids:
            continue
        key = frozenset((u.person_a_id, u.person_b_id))
        if key in fam_index:
            continue
        fam = {"members": [u.person_a_id, u.person_b_id], "children": [], "union": u}
        fam_index[key] = fam
        fams.append(fam)

    for child, parents in graph.parents.items():
        if child not in ids:
            continue
        plist = sorted(parents, key=str)
        key = frozenset(plist[:2])
        fam = fam_index.get(key)
        if fam is None:
            fam = {"members": plist[:2], "children": [], "union": None}
            fam_index[key] = fam
            fams.append(fam)
        fam["children"].append(child)

    fam_ids = {id(f): f"@F{i}@" for i, f in enumerate(fams, start=1)}
    fams_of: dict[UUID, list[str]] = {}
    famc_of: dict[UUID, list[str]] = {}
    for f in fams:
        for m in f["members"]:
            fams_of.setdefault(m, []).append(fam_ids[id(f)])
        for c in f["children"]:
            famc_of.setdefault(c, []).append(fam_ids[id(f)])

    for pid, p in graph.persons.items():
        lines.append(f"0 {ids[pid]} INDI")
        last = _clean(p.last_name or "")
        lines.append(f"1 NAME {_clean(p.first_name)} /{last}/")
        lines.append(f"2 GIVN {_clean(p.first_name)}")
        if last:
            lines.append(f"2 SURN {last}")
        if p.traditional_name:
            lines.append(f"1 NAME {_clean(p.traditional_name)}")
            lines.append("2 TYPE aka")
        if p.nickname:
            lines.append(f"1 NICK {_clean(p.nickname)}")
        lines.append(f"1 SEX {p.sex if p.sex in ('M', 'F') else 'U'}")
        show_dates = include_living_dates or not p.is_living
        bd = _date(p.birth_date, p.birth_year) if show_dates else None
        if bd or p.birth_place:
            lines.append("1 BIRT")
            if bd:
                lines.append(f"2 DATE {bd}")
            if p.birth_place:
                lines.append(f"2 PLAC {_clean(p.birth_place)}")
        if not p.is_living:
            dd = _date(p.death_date, p.death_year)
            lines.append("1 DEAT Y" if not (dd or p.death_place) else "1 DEAT")
            if dd:
                lines.append(f"2 DATE {dd}")
            if p.death_place:
                lines.append(f"2 PLAC {_clean(p.death_place)}")
        for badge in graph.badges(pid):
            lines.append(f"1 TITL {_clean(badge.name)}")
        if p.village:
            lines.append("1 RESI")
            lines.append(f"2 PLAC {_clean(p.village)}")
        if p.biography:
            lines.append(f"1 NOTE {_clean(p.biography)[:240]}")
        for f in famc_of.get(pid, []):
            lines.append(f"1 FAMC {f}")
        for f in fams_of.get(pid, []):
            lines.append(f"1 FAMS {f}")

    for f in fams:
        lines.append(f"0 {fam_ids[id(f)]} FAM")
        # GEDCOM n'admet qu'un HUSB et une WIFE : l'homme en HUSB, l'autre membre en WIFE.
        members = sorted(f["members"], key=lambda m: graph.persons[m].sex != "M")
        slots = {}
        for m in members:
            preferred = "HUSB" if graph.persons[m].sex == "M" else "WIFE"
            tag = preferred if preferred not in slots else ({"HUSB", "WIFE"} - {preferred}).pop()
            slots[tag] = m
        for tag in ("HUSB", "WIFE"):
            if tag in slots:
                lines.append(f"1 {tag} {ids[slots[tag]]}")
        u = f["union"]
        if u is not None:
            md = _date(u.start_date, None)
            lines.append("1 MARR")
            if md:
                lines.append(f"2 DATE {md}")
            lines.append(f"2 TYPE {u.kind}")
            if u.end_reason == "divorce":
                lines.append("1 DIV Y")
        for c in f["children"]:
            lines.append(f"1 CHIL {ids[c]}")

    lines.append("0 TRLR")
    return "\n".join(lines) + "\n"
