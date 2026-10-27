"""Import GEDCOM 5.5.1 : lit un fichier .ged et crée les personnes, unions et filiations.

Le format GEDCOM est une suite de lignes « niveau [@ref@] ÉTIQUETTE [valeur] ».
On ne retient que ce que Sheenu sait représenter : identité, dates et lieux de
naissance et de décès, surnom, note ; unions (FAM) et enfants.
"""

import re
from dataclasses import dataclass, field
from datetime import date

MONTHS = {
    m: i
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}
LINE = re.compile(r"^\s*(\d+)\s+(@[^@]+@\s+)?(\w+)\s?(.*)$")


@dataclass
class GedIndividual:
    ref: str
    first_name: str = ""
    last_name: str | None = None
    nickname: str | None = None
    sex: str = "U"
    birth_date: date | None = None
    birth_year: int | None = None
    birth_place: str | None = None
    death_date: date | None = None
    death_year: int | None = None
    death_place: str | None = None
    is_living: bool = True
    note: str | None = None


@dataclass
class GedFamily:
    ref: str
    partners: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    married: bool = False
    marriage_date: date | None = None
    divorced: bool = False


def parse_date(value: str) -> tuple[date | None, int | None]:
    """« 12 MAR 1950 » → date ; « ABT 1950 », « 1950 » → année seule."""
    words = value.upper().replace("ABT", "").replace("EST", "").replace("CAL", "").split()
    try:
        if len(words) == 3 and words[1] in MONTHS:
            return date(int(words[2]), MONTHS[words[1]], int(words[0])), None
    except ValueError:
        pass
    years = [int(w) for w in words if w.isdigit() and len(w) == 4]
    return None, (years[-1] if years else None)


def parse(text: str) -> tuple[dict[str, GedIndividual], list[GedFamily]]:
    individuals: dict[str, GedIndividual] = {}
    families: list[GedFamily] = []
    current: GedIndividual | GedFamily | None = None
    event: str | None = None  # BIRT, DEAT, MARR… en cours au niveau 1

    for raw in text.splitlines():
        m = LINE.match(raw.lstrip("﻿"))
        if not m:
            continue
        level, ref, tag, value = (
            int(m.group(1)),
            (m.group(2) or "").strip(),
            m.group(3),
            m.group(4).strip(),
        )

        if level == 0:
            event = None
            if tag == "INDI":
                current = individuals.setdefault(ref, GedIndividual(ref=ref))
            elif tag == "FAM":
                current = GedFamily(ref=ref)
                families.append(current)
            else:
                current = None
            continue

        if isinstance(current, GedIndividual):
            if level == 1:
                event = tag
                if tag == "NAME" and not current.first_name:
                    given, _, rest = value.partition("/")
                    current.first_name = given.strip() or "?"
                    current.last_name = rest.split("/")[0].strip() or None
                elif tag == "SEX":
                    current.sex = value[:1] if value[:1] in ("M", "F") else "U"
                elif tag == "NICK":
                    current.nickname = value or None
                elif tag == "DEAT":
                    current.is_living = False
                elif tag == "NOTE":
                    current.note = value or None
            elif level == 2 and event in ("BIRT", "DEAT"):
                if tag == "DATE":
                    d, y = parse_date(value)
                    if event == "BIRT":
                        current.birth_date, current.birth_year = d, y
                    else:
                        current.death_date, current.death_year = d, y
                elif tag == "PLAC":
                    if event == "BIRT":
                        current.birth_place = value
                    else:
                        current.death_place = value
            elif level == 2 and event == "NOTE" and tag in ("CONT", "CONC") and current.note:
                current.note += ("\n" if tag == "CONT" else "") + value

        elif isinstance(current, GedFamily):
            if level == 1:
                event = tag
                if tag in ("HUSB", "WIFE"):
                    current.partners.append(value)
                elif tag == "CHIL":
                    current.children.append(value)
                elif tag == "MARR":
                    current.married = True
                elif tag == "DIV":
                    current.divorced = True
            elif level == 2 and event == "MARR" and tag == "DATE":
                current.marriage_date, _ = parse_date(value)

    return individuals, families
