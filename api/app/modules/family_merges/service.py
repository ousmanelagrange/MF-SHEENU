"""Réunion de deux familles : la famille source rejoint la famille d'accueil.

Déroulé, dans une seule transaction :
1. lecture de tout l'arbre source (contexte RLS = famille source) ;
2. écriture dans la famille d'accueil (contexte RLS = famille d'accueil) :
   - une copie de chaque personne, sauf les membres déjà présents dans les deux familles,
     dont la fiche source est fusionnée dans leur fiche d'accueil ;
   - filiations, unions et titres (regroupés par nom), en évitant les doublons ;
   - les membres inscrits rejoignent la famille d'accueil (voir NEW_ROLE) ;
   - les délégations sont conservées ;
3. la famille source est marquée « réunie » et disparaît des listes.

Collectes, propositions et journal restent attachés à la famille source (historique).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.db import set_family_context
from app.models import (
    Delegation,
    Family,
    FamilyUnion,
    Membership,
    ParentChild,
    Person,
    Role,
    TitleDefinition,
    TitleHolding,
    User,
)
from app.shared.audit import snapshot

# Rôle dans la famille d'accueil selon le rôle dans la famille source : un administrateur
# devient chef de sa branche (il garde la main sur les siens sans gouverner la grande famille) ;
# les rôles propres à l'association source (trésorier, secrétaire) redeviennent membres.
NEW_ROLE = {
    Role.ADMIN: Role.BRANCH_HEAD,
    Role.BRANCH_HEAD: Role.BRANCH_HEAD,
    Role.TREASURER: Role.MEMBER,
    Role.SECRETARY: Role.MEMBER,
    Role.MEMBER: Role.MEMBER,
}

PERSON_FIELDS = [
    c.key for c in Person.__table__.columns if c.key not in ("id", "family_id", "archived_at")
]


def _read_source(db, source: Family) -> dict:  # noqa: ANN001
    set_family_context(db, source.id)
    return {
        "persons": list(
            db.scalars(
                select(Person).where(Person.family_id == source.id, Person.archived_at.is_(None))
            )
        ),
        "links": list(db.scalars(select(ParentChild).where(ParentChild.family_id == source.id))),
        "unions": list(db.scalars(select(FamilyUnion).where(FamilyUnion.family_id == source.id))),
        "titles": {
            t.id: t
            for t in db.scalars(
                select(TitleDefinition).where(TitleDefinition.family_id == source.id)
            )
        },
        "holdings": list(
            db.scalars(select(TitleHolding).where(TitleHolding.family_id == source.id))
        ),
        "delegations": list(
            db.scalars(select(Delegation).where(Delegation.family_id == source.id))
        ),
        "memberships": list(
            db.scalars(select(Membership).where(Membership.family_id == source.id))
        ),
    }


def merge_families(db, source: Family, target: Family, actor: User) -> dict:  # noqa: ANN001
    """Fait entrer la famille `source` dans `target` et renvoie un bilan chiffré."""
    src = _read_source(db, source)
    set_family_context(db, target.id)

    target_members = {
        m.user_id: m
        for m in db.scalars(select(Membership).where(Membership.family_id == target.id))
    }

    # 1. Personnes : fiche commune pour les comptes présents des deux côtés, copie sinon.
    person_map: dict[UUID, UUID] = {}
    merged_accounts = 0
    for m in src["memberships"]:
        existing = target_members.get(m.user_id)
        if m.person_id and existing and existing.person_id:
            person_map[m.person_id] = existing.person_id
            merged_accounts += 1
    by_id = {p.id: p for p in src["persons"]}
    for source_pid, target_pid in person_map.items():
        kept = db.get(Person, target_pid)
        for name in PERSON_FIELDS:  # compléter les champs vides de la fiche conservée
            if getattr(kept, name) in (None, "") and getattr(by_id[source_pid], name) not in (
                None,
                "",
            ):
                setattr(kept, name, getattr(by_id[source_pid], name))
    for p in src["persons"]:
        if p.id in person_map:
            continue
        copy = Person(family_id=target.id, **{name: getattr(p, name) for name in PERSON_FIELDS})
        db.add(copy)
        db.flush()
        person_map[p.id] = copy.id

    # 2. Filiations et unions, sans doublon ni auto-lien.
    existing_links = {
        (lk.parent_id, lk.child_id)
        for lk in db.scalars(select(ParentChild).where(ParentChild.family_id == target.id))
    }
    links = 0
    for lk in src["links"]:
        pair = (person_map.get(lk.parent_id), person_map.get(lk.child_id))
        if None in pair or pair[0] == pair[1] or pair in existing_links:
            continue
        db.add(
            ParentChild(
                family_id=target.id,
                parent_id=pair[0],
                child_id=pair[1],
                kind=lk.kind,
                certainty=lk.certainty,
                source=lk.source,
            )
        )
        existing_links.add(pair)
        links += 1

    existing_unions = {
        frozenset((u.person_a_id, u.person_b_id))
        for u in db.scalars(select(FamilyUnion).where(FamilyUnion.family_id == target.id))
    }
    unions = 0
    for u in src["unions"]:
        a, b = person_map.get(u.person_a_id), person_map.get(u.person_b_id)
        if not a or not b or a == b or frozenset((a, b)) in existing_unions:
            continue
        db.add(
            FamilyUnion(
                family_id=target.id,
                person_a_id=a,
                person_b_id=b,
                kind=u.kind,
                rank=u.rank,
                start_date=u.start_date,
                end_date=u.end_date,
                end_reason=u.end_reason,
                certainty=u.certainty,
            )
        )
        existing_unions.add(frozenset((a, b)))
        unions += 1

    # 3. Titres : regroupés par nom, créés s'ils n'existent pas encore.
    target_titles = {
        t.name.lower(): t
        for t in db.scalars(select(TitleDefinition).where(TitleDefinition.family_id == target.id))
    }
    title_map: dict[UUID, UUID] = {}
    for t in src["titles"].values():
        found = target_titles.get(t.name.lower())
        if not found:
            found = TitleDefinition(
                family_id=target.id,
                name=t.name,
                abbreviation=t.abbreviation,
                precedence=t.precedence,
                badge_color=t.badge_color,
                hereditary=t.hereditary,
                description=t.description,
            )
            db.add(found)
            db.flush()
            target_titles[t.name.lower()] = found
        title_map[t.id] = found.id
    for h in src["holdings"]:
        if h.person_id in person_map and h.title_id in title_map:
            db.add(
                TitleHolding(
                    family_id=target.id,
                    title_id=title_map[h.title_id],
                    person_id=person_map[h.person_id],
                    conferred_by=h.conferred_by,
                    conferred_on=h.conferred_on,
                    ended_on=h.ended_on,
                    predecessor_id=person_map.get(h.predecessor_id),
                    notes=h.notes,
                )
            )

    # 4. Membres : ceux qui n'étaient pas encore dans la famille d'accueil la rejoignent.
    membership_map: dict[UUID, UUID] = {}
    new_members = 0
    for m in src["memberships"]:
        existing = target_members.get(m.user_id)
        if existing:
            membership_map[m.id] = existing.id
            continue
        role = NEW_ROLE.get(m.role, Role.MEMBER)
        branch = person_map.get(m.branch_person_id or source.root_person_id or m.person_id)
        joined = Membership(
            family_id=target.id,
            user_id=m.user_id,
            person_id=person_map.get(m.person_id),
            role=role,
            branch_person_id=branch if role == Role.BRANCH_HEAD else None,
        )
        db.add(joined)
        db.flush()
        membership_map[m.id] = joined.id
        new_members += 1

    # 5. Délégations
    for d in src["delegations"]:
        if d.person_id in person_map and d.membership_id in membership_map:
            db.add(
                Delegation(
                    family_id=target.id,
                    person_id=person_map[d.person_id],
                    membership_id=membership_map[d.membership_id],
                    created_by=d.created_by,
                )
            )

    db.flush()
    source.merged_into_id = target.id
    source.merged_at = datetime.now(UTC)
    return {
        "persons": len(src["persons"]),
        "links": links,
        "unions": unions,
        "titles": len(title_map),
        "new_members": new_members,
        "merged_accounts": merged_accounts,
        "source_root_id": str(person_map[source.root_person_id])
        if source.root_person_id in person_map
        else None,
        "source_family": snapshot(source)["name"],
    }
