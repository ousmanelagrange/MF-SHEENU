"""Mise en forme des fiches pour l'API.

Transforme une personne du graphe en réponse JSON, en appliquant la confidentialité
des coordonnées (RG-21) et le droit de modification de l'utilisateur courant.
"""

from datetime import datetime
from uuid import UUID

from app.core.deps import FamilyContext
from app.genealogy.graph import FamilyGraph
from app.models import Person
from app.modules.persons.schemas import PersonDetail, PersonOut, RelativeLink, SpouseLink


def contact_visible(ctx: FamilyContext, graph: FamilyGraph, p: Person) -> bool:
    """RG-21 : visibilité des coordonnées choisie par la personne."""
    if ctx.membership.person_id == p.id:
        return True
    vis = p.contact_visibility
    if vis == "family":
        return True
    if vis == "board":
        return ctx.is_board
    if vis == "branch":
        if ctx.is_board:
            return True
        mine = graph.branch_of(ctx.membership.person_id) if ctx.membership.person_id else None
        return mine is not None and mine == graph.branch_of(p.id)
    return False


def person_out(ctx: FamilyContext, graph: FamilyGraph, pid: UUID) -> PersonOut:
    p = graph.persons[pid]
    show = contact_visible(ctx, graph, p)
    return PersonOut(
        **graph.summary(pid).model_dump(),
        nickname=p.nickname,
        birth_date=p.birth_date,
        birth_place=p.birth_place,
        death_date=p.death_date,
        death_place=p.death_place,
        village=p.village,
        country=p.country,
        biography=p.biography,
        phone=p.phone if show else None,
        email=p.email if show else None,
        contact_visibility=p.contact_visibility,
        created_at=p.created_at,
        updated_at=p.updated_at,
        can_edit=graph.can_write(ctx.membership, pid),
    )


def person_detail(ctx: FamilyContext, graph: FamilyGraph, pid: UUID) -> PersonDetail:
    base = person_out(ctx, graph, pid)
    links = [link for link in graph.parent_links if pid in (link.parent_id, link.child_id)]
    parents = [
        RelativeLink(
            relation_id=link.id,
            kind=link.kind,
            certainty=link.certainty,
            person=graph.summary(link.parent_id),
        )
        for link in links
        if link.child_id == pid and link.parent_id in graph.persons
    ]
    children = [
        RelativeLink(
            relation_id=link.id,
            kind=link.kind,
            certainty=link.certainty,
            person=graph.summary(link.child_id),
        )
        for link in links
        if link.parent_id == pid and link.child_id in graph.persons
    ]
    children.sort(key=lambda r: graph.precedence_key(r.person.id)[2:])
    spouses = []
    for u in graph.unions:
        if pid not in (u.person_a_id, u.person_b_id):
            continue
        other = u.person_b_id if u.person_a_id == pid else u.person_a_id
        if other not in graph.persons:
            continue
        spouses.append(
            SpouseLink(
                union_id=u.id,
                kind=u.kind,
                rank=u.rank,
                start_date=u.start_date,
                end_date=u.end_date,
                end_reason=u.end_reason,
                person=graph.summary(other),
            )
        )
    spouses.sort(key=lambda s: (s.rank or 99, s.start_date or datetime.max.date()))
    siblings = sorted(graph.siblings(pid), key=lambda s: graph.precedence_key(s)[2:])
    return PersonDetail(
        **base.model_dump(),
        parents=parents,
        children=children,
        spouses=spouses,
        siblings=[graph.summary(s) for s in siblings],
    )
