"""Logique métier des liens : filiations (parent → enfant) et unions.

Mêmes principes que persons/service.py : règles métier et audit ici, périmètre et
commit chez l'appelant.
"""

from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import bad_request, conflict, not_found
from app.genealogy.graph import load_graph
from app.models import FamilyUnion, ParentChild
from app.modules.relations.schemas import ParentChildCreate, UnionCreate
from app.shared import audit


def add_parent_child(ctx: FamilyContext, body: ParentChildCreate) -> ParentChild:
    """Ajoute « parent → enfant » en respectant RG-08 (2 parents biologiques) et RG-09 (pas de cycle)."""
    graph = load_graph(ctx)
    for pid in (body.parent_id, body.child_id):
        if pid not in graph.persons:
            raise not_found("Personne")
    if body.parent_id == body.child_id:
        raise bad_request("validation_error", "Une personne ne peut pas être son propre parent.")
    if graph.is_descendant(body.parent_id, body.child_id):
        raise conflict("cycle_detected", "Ce lien créerait une boucle dans l'arbre.")
    exists = ctx.db.scalar(
        select(ParentChild).where(
            ParentChild.parent_id == body.parent_id, ParentChild.child_id == body.child_id
        )
    )
    if exists:
        raise conflict("already_exists", "Ce lien existe déjà.")
    if body.kind == "biological":
        biological = [
            link
            for link in graph.parent_links
            if link.child_id == body.child_id and link.kind == "biological"
        ]
        if len(biological) >= 2:
            raise conflict("too_many_parents", "Cette personne a déjà deux parents biologiques.")

    link = ParentChild(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(link)
    ctx.db.flush()
    audit.record(ctx, "create", "parent_child", link.id, after=audit.snapshot(link))
    return link


def get_link(ctx: FamilyContext, link_id: UUID) -> ParentChild:
    link = ctx.db.get(ParentChild, link_id)
    if link is None or link.family_id != ctx.family.id:
        raise not_found("Lien")
    return link


def delete_parent_child(ctx: FamilyContext, link_id: UUID) -> None:
    link = get_link(ctx, link_id)
    audit.record(ctx, "delete", "parent_child", link.id, before=audit.snapshot(link))
    ctx.db.delete(link)


def add_union(ctx: FamilyContext, body: UnionCreate) -> FamilyUnion:
    """Unit deux personnes distinctes (RG-10). Plusieurs unions par personne sont permises."""
    if body.person_a_id == body.person_b_id:
        raise bad_request("validation_error", "Une union relie deux personnes distinctes.")
    graph = load_graph(ctx)
    for pid in (body.person_a_id, body.person_b_id):
        if pid not in graph.persons:
            raise not_found("Personne")
    if body.person_b_id in graph.spouses.get(body.person_a_id, set()):
        raise conflict("already_exists", "Ces deux personnes sont déjà unies.")
    union = FamilyUnion(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(union)
    ctx.db.flush()
    audit.record(ctx, "create", "union", union.id, after=audit.snapshot(union))
    return union


def get_union(ctx: FamilyContext, union_id: UUID) -> FamilyUnion:
    union = ctx.db.get(FamilyUnion, union_id)
    if union is None or union.family_id != ctx.family.id:
        raise not_found("Union")
    return union


def delete_union(ctx: FamilyContext, union_id: UUID) -> None:
    union = get_union(ctx, union_id)
    audit.record(ctx, "delete", "union", union.id, before=audit.snapshot(union))
    ctx.db.delete(union)
