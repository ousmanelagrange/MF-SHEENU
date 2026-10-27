"""Gestion des données de l'arbre : import GEDCOM, détection des doublons, fusion de fiches."""

import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import bad_request, conflict
from app.genealogy.graph import FamilyGraph, load_graph
from app.models import (
    Delegation,
    FamilyUnion,
    Membership,
    ParentChild,
    Person,
    TitleHolding,
)
from app.modules.data.gedcom_import import parse
from app.modules.persons import service as persons_service
from app.shared import audit

# ---------- Import ----------


def import_gedcom(ctx: FamilyContext, text: str) -> dict:
    """Crée les personnes, unions et filiations du fichier. Renvoie un bilan chiffré.

    L'import ajoute à l'arbre existant : il ne fusionne pas automatiquement. Les doublons
    éventuels apparaissent ensuite dans la liste des doublons, où l'on peut les fusionner.
    """
    individuals, families = parse(text)
    if not individuals:
        raise bad_request("invalid_gedcom", "Aucune personne trouvée dans ce fichier GEDCOM.")

    ids: dict[str, UUID] = {}
    for ind in individuals.values():
        person = Person(
            family_id=ctx.family.id,
            first_name=ind.first_name or "?",
            last_name=ind.last_name,
            nickname=ind.nickname,
            sex=ind.sex,
            birth_date=ind.birth_date,
            birth_year=ind.birth_year,
            birth_place=ind.birth_place,
            death_date=ind.death_date,
            death_year=ind.death_year,
            death_place=ind.death_place,
            is_living=ind.is_living,
            biography=ind.note,
            created_by=ctx.user.id,
        )
        ctx.db.add(person)
        ctx.db.flush()
        ids[ind.ref] = person.id

    unions = links = 0
    seen_links: set[tuple[UUID, UUID]] = set()
    for fam in families:
        partners = [ids[r] for r in fam.partners if r in ids]
        if len(partners) == 2 and partners[0] != partners[1]:
            ctx.db.add(
                FamilyUnion(
                    family_id=ctx.family.id,
                    person_a_id=partners[0],
                    person_b_id=partners[1],
                    start_date=fam.marriage_date,
                    end_reason="divorce" if fam.divorced else None,
                )
            )
            unions += 1
        for child_ref in fam.children:
            child = ids.get(child_ref)
            for parent in partners:
                if child and parent != child and (parent, child) not in seen_links:
                    seen_links.add((parent, child))
                    ctx.db.add(
                        ParentChild(family_id=ctx.family.id, parent_id=parent, child_id=child)
                    )
                    links += 1
    ctx.db.flush()
    summary = {"persons": len(ids), "unions": unions, "links": links}
    audit.record(ctx, "import", "family", ctx.family.id, after=summary)
    return summary


# ---------- Doublons ----------


def normalize(text: str | None) -> str:
    """Minuscules, sans accents ni espaces superflus : « Aïssatou » = « aissatou »."""
    if not text:
        return ""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(plain.lower().split())


def birth_year(p: Person) -> int | None:
    return p.birth_year or (p.birth_date.year if p.birth_date else None)


def find_duplicates(graph: FamilyGraph) -> list[tuple[UUID, UUID]]:
    """Paires de fiches qui semblent être la même personne.

    Critères : même prénom et même nom (sans accents), années de naissance compatibles
    (écart de 2 ans au plus, ou inconnue), et aucune filiation ni union entre les deux.
    """
    groups: dict[tuple[str, str], list[UUID]] = {}
    for pid, p in graph.persons.items():
        key = (normalize(p.first_name), normalize(p.last_name))
        groups.setdefault(key, []).append(pid)

    pairs = []
    for members in groups.values():
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                ya, yb = birth_year(graph.persons[a]), birth_year(graph.persons[b])
                if ya and yb and abs(ya - yb) > 2:
                    continue
                if graph.is_descendant(a, b) or graph.is_descendant(b, a):
                    continue
                if b in graph.spouses.get(a, set()):
                    continue
                pairs.append((a, b))
    return pairs


# ---------- Fusion ----------

FILLABLE = (
    "last_name",
    "traditional_name",
    "nickname",
    "birth_date",
    "birth_year",
    "birth_place",
    "death_date",
    "death_year",
    "death_place",
    "village",
    "country",
    "biography",
    "photo_url",
    "phone",
    "email",
)


def merge_persons(ctx: FamilyContext, keep_id: UUID, other_id: UUID) -> Person:
    """Fusionne `other` dans `keep` : liens, unions, titres et délégations passent sur `keep`,
    les champs vides de `keep` sont complétés, puis `other` est archivée."""
    if keep_id == other_id:
        raise bad_request("validation_error", "Choisissez deux fiches différentes.")
    keep = persons_service.get_person(ctx, keep_id)
    other = persons_service.get_person(ctx, other_id)
    graph = load_graph(ctx)
    if graph.is_descendant(keep_id, other_id) or graph.is_descendant(other_id, keep_id):
        raise conflict("cycle_detected", "L'une est l'ascendante de l'autre : fusion impossible.")

    db = ctx.db
    members = {
        m.person_id: m
        for m in db.scalars(
            select(Membership).where(
                Membership.family_id == ctx.family.id,
                Membership.person_id.in_([keep_id, other_id]),
            )
        )
    }
    if keep_id in members and other_id in members:
        raise conflict("both_have_accounts", "Les deux fiches sont liées à des comptes différents.")
    if other_id in members:
        members[other_id].person_id = keep_id

    before = audit.snapshot(keep)
    for name in FILLABLE:
        if getattr(keep, name) in (None, "") and getattr(other, name) not in (None, ""):
            setattr(keep, name, getattr(other, name))
    if not other.is_living:
        keep.is_living = False

    # Filiations : on redirige vers `keep`, en supprimant les doublons et les auto-liens.
    existing = {(link.parent_id, link.child_id) for link in graph.parent_links}
    for link in db.scalars(
        select(ParentChild).where(
            (ParentChild.parent_id == other_id) | (ParentChild.child_id == other_id)
        )
    ):
        new = (
            keep_id if link.parent_id == other_id else link.parent_id,
            keep_id if link.child_id == other_id else link.child_id,
        )
        if new[0] == new[1] or new in existing:
            db.delete(link)
        else:
            link.parent_id, link.child_id = new
            existing.add(new)

    # Unions : même principe.
    pairs = {frozenset((u.person_a_id, u.person_b_id)) for u in graph.unions}
    for union in db.scalars(
        select(FamilyUnion).where(
            (FamilyUnion.person_a_id == other_id) | (FamilyUnion.person_b_id == other_id)
        )
    ):
        a = keep_id if union.person_a_id == other_id else union.person_a_id
        b = keep_id if union.person_b_id == other_id else union.person_b_id
        if a == b or frozenset((a, b)) in pairs:
            db.delete(union)
        else:
            union.person_a_id, union.person_b_id = a, b
            pairs.add(frozenset((a, b)))

    for holding in db.scalars(select(TitleHolding).where(TitleHolding.person_id == other_id)):
        holding.person_id = keep_id
    for holding in db.scalars(select(TitleHolding).where(TitleHolding.predecessor_id == other_id)):
        holding.predecessor_id = keep_id

    delegated = {
        d.membership_id
        for d in db.scalars(select(Delegation).where(Delegation.person_id == keep_id))
    }
    for d in db.scalars(select(Delegation).where(Delegation.person_id == other_id)):
        if d.membership_id in delegated:
            db.delete(d)
        else:
            d.person_id = keep_id

    if ctx.family.root_person_id == other_id:
        ctx.family.root_person_id = keep_id
    other.archived_at = datetime.now(UTC)
    db.flush()
    audit.record(
        ctx, "merge", "person", keep.id, before, audit.snapshot(keep) | {"merged": str(other_id)}
    )
    return keep
