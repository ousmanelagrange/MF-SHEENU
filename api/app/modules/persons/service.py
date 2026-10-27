"""Logique métier des personnes : création, modification, archivage.

Ces fonctions valident les règles métier et écrivent l'audit, mais ne vérifient pas
le périmètre de l'utilisateur : c'est le rôle de l'appelant (route directe, ou
validation d'une proposition par un chef de branche). Elles ne font pas de commit.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import bad_request, forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import FamilyUnion, Membership, ParentChild, Person
from app.modules.persons.schemas import PersonCreate, PersonUpdate
from app.shared import audit


def get_person(ctx: FamilyContext, pid: UUID) -> Person:
    """Personne active de la famille courante, sinon 404."""
    p = ctx.db.get(Person, pid)
    if p is None or p.family_id != ctx.family.id or p.archived_at is not None:
        raise not_found("Personne")
    return p


def create_person(ctx: FamilyContext, body: PersonCreate) -> Person:
    """Crée une fiche, et la rattache directement à ses parents et à son conjoint s'ils sont donnés."""
    graph = load_graph(ctx)
    for related_id in [*body.parent_ids, *([body.spouse_id] if body.spouse_id else [])]:
        if related_id not in graph.persons:
            raise not_found("Personne liée")
    if len(set(body.parent_ids)) != len(body.parent_ids):
        raise bad_request("validation_error", "Parents en double.")

    fields = body.model_dump(exclude={"parent_ids", "spouse_id", "union_kind", "union_rank"})
    person = Person(family_id=ctx.family.id, created_by=ctx.user.id, **fields)
    if person.death_date or person.death_year:
        person.is_living = False
    ctx.db.add(person)
    ctx.db.flush()
    audit.record(ctx, "create", "person", person.id, after=audit.snapshot(person))

    for parent_id in body.parent_ids:
        link = ParentChild(family_id=ctx.family.id, parent_id=parent_id, child_id=person.id)
        ctx.db.add(link)
        ctx.db.flush()
        audit.record(ctx, "create", "parent_child", link.id, after=audit.snapshot(link))

    if body.spouse_id:
        union = FamilyUnion(
            family_id=ctx.family.id,
            person_a_id=body.spouse_id,
            person_b_id=person.id,
            kind=body.union_kind,
            rank=body.union_rank,
        )
        ctx.db.add(union)
        ctx.db.flush()
        audit.record(ctx, "create", "union", union.id, after=audit.snapshot(union))
    return person


def update_person(ctx: FamilyContext, pid: UUID, body: PersonUpdate) -> Person:
    """Modifie les champs fournis. Une date de décès rend la personne « décédée »."""
    p = get_person(ctx, pid)
    before = audit.snapshot(p)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    if p.death_date or p.death_year:
        p.is_living = False
    p.updated_at = datetime.now(UTC)
    audit.record(ctx, "update", "person", p.id, before, audit.snapshot(p))
    return p


def archive_person(ctx: FamilyContext, pid: UUID) -> None:
    """RG-16 : on archive, on ne supprime jamais. Interdit pour la racine et un compte lié."""
    p = get_person(ctx, pid)
    if ctx.family.root_person_id == pid:
        raise bad_request("is_root", "Impossible d'archiver l'ancêtre racine.")
    linked = ctx.db.scalar(
        select(Membership).where(Membership.family_id == ctx.family.id, Membership.person_id == pid)
    )
    if linked:
        raise forbidden("Cette fiche est liée au compte d'un membre.")
    before = audit.snapshot(p)
    p.archived_at = datetime.now(UTC)
    audit.record(ctx, "archive", "person", p.id, before, audit.snapshot(p))
