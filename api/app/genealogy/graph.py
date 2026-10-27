"""Graphe familial en mémoire : générations, ascendants, parenté, préséance, périmètre.

Une famille de quelques milliers de personnes tient largement en mémoire : on charge
personnes et liens une fois par requête, puis tous les calculs sont instantanés.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.genealogy.kinship import blood_label, spouse_label
from app.models import (
    Delegation,
    FamilyUnion,
    Membership,
    ParentChild,
    Person,
    Role,
    TitleDefinition,
    TitleHolding,
)
from app.modules.persons.schemas import PersonSummary, TitleBadge

INF = 10**9


@dataclass
class FamilyGraph:
    persons: dict[UUID, Person]
    parent_links: list[ParentChild]
    unions: list[FamilyUnion]
    titles: dict[UUID, TitleDefinition]
    holdings: list[TitleHolding]
    root_id: UUID | None
    accounts: dict[UUID, UUID] = field(default_factory=dict)  # person_id -> user_id
    delegations: dict[UUID, set[UUID]] = field(default_factory=dict)  # membership_id -> person_ids

    parents: dict[UUID, set[UUID]] = field(default_factory=lambda: defaultdict(set))
    children: dict[UUID, set[UUID]] = field(default_factory=lambda: defaultdict(set))
    spouses: dict[UUID, set[UUID]] = field(default_factory=lambda: defaultdict(set))
    holdings_by_person: dict[UUID, list[TitleHolding]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _generations: dict[UUID, int] | None = None
    _branch: dict[UUID, UUID | None] | None = None

    def __post_init__(self) -> None:
        for link in self.parent_links:
            if link.parent_id in self.persons and link.child_id in self.persons:
                self.parents[link.child_id].add(link.parent_id)
                self.children[link.parent_id].add(link.child_id)
        for u in self.unions:
            if u.person_a_id in self.persons and u.person_b_id in self.persons:
                self.spouses[u.person_a_id].add(u.person_b_id)
                self.spouses[u.person_b_id].add(u.person_a_id)
        for h in self.holdings:
            if h.person_id in self.persons and h.title_id in self.titles:
                self.holdings_by_person[h.person_id].append(h)

    # ---------- chargement ----------

    @classmethod
    def load(cls, db: Session, family_id: UUID, root_id: UUID | None) -> FamilyGraph:
        persons = {
            p.id: p
            for p in db.scalars(
                select(Person).where(Person.family_id == family_id, Person.archived_at.is_(None))
            )
        }
        links = list(db.scalars(select(ParentChild).where(ParentChild.family_id == family_id)))
        unions = list(db.scalars(select(FamilyUnion).where(FamilyUnion.family_id == family_id)))
        titles = {
            t.id: t
            for t in db.scalars(
                select(TitleDefinition).where(TitleDefinition.family_id == family_id)
            )
        }
        holdings = list(db.scalars(select(TitleHolding).where(TitleHolding.family_id == family_id)))
        accounts = {
            m.person_id: m.user_id
            for m in db.scalars(
                select(Membership).where(
                    Membership.family_id == family_id, Membership.person_id.is_not(None)
                )
            )
        }
        delegations: dict[UUID, set[UUID]] = defaultdict(set)
        for d in db.scalars(select(Delegation).where(Delegation.family_id == family_id)):
            delegations[d.membership_id].add(d.person_id)
        return cls(persons, links, unions, titles, holdings, root_id, accounts, dict(delegations))

    # ---------- parcours ----------

    def ancestors(self, pid: UUID, max_depth: int = 50) -> dict[UUID, int]:
        """Ascendants avec la plus courte distance (pid lui-même exclu)."""
        dist: dict[UUID, int] = {}
        queue = deque([(pid, 0)])
        while queue:
            cur, d = queue.popleft()
            if d >= max_depth:
                continue
            for par in self.parents.get(cur, ()):
                if par not in dist:
                    dist[par] = d + 1
                    queue.append((par, d + 1))
        dist.pop(pid, None)
        return dist

    def descendants(self, pid: UUID, max_depth: int = 50) -> dict[UUID, int]:
        dist: dict[UUID, int] = {}
        queue = deque([(pid, 0)])
        while queue:
            cur, d = queue.popleft()
            if d >= max_depth:
                continue
            for ch in self.children.get(cur, ()):
                if ch not in dist:
                    dist[ch] = d + 1
                    queue.append((ch, d + 1))
        dist.pop(pid, None)
        return dist

    def is_descendant(self, candidate: UUID, of: UUID) -> bool:
        return candidate == of or candidate in self.descendants(of)

    def siblings(self, pid: UUID) -> set[UUID]:
        result: set[UUID] = set()
        for par in self.parents.get(pid, ()):
            result |= self.children.get(par, set())
        result.discard(pid)
        return result

    # ---------- générations ----------

    def generations(self) -> dict[UUID, int]:
        """Génération de chaque personne (racine = 1) — §2.3."""
        if self._generations is not None:
            return self._generations
        gen: dict[UUID, int] = {}
        starts: list[UUID]
        if self.root_id and self.root_id in self.persons:
            starts = [self.root_id]
        else:
            starts = [p for p in self.persons if not self.parents.get(p)]
        queue = deque()
        for s in starts:
            gen[s] = 1
            queue.append(s)
        while queue:
            cur = queue.popleft()
            for ch in self.children.get(cur, ()):
                if ch not in gen:
                    gen[ch] = gen[cur] + 1
                    queue.append(ch)
        # Ancêtres au-dessus de la racine : générations 0, -1, …
        if self.root_id and self.root_id in self.persons:
            for anc, d in self.ancestors(self.root_id).items():
                gen.setdefault(anc, 1 - d)
        # Conjoints hors lignée : génération du conjoint (plusieurs passes pour les chaînes).
        for _ in range(3):
            for pid in self.persons:
                if pid in gen:
                    continue
                spouse_gens = [gen[s] for s in self.spouses.get(pid, ()) if s in gen]
                if spouse_gens:
                    gen[pid] = min(spouse_gens)
                    continue
                child_gens = [gen[c] - 1 for c in self.children.get(pid, ()) if c in gen]
                if child_gens:
                    gen[pid] = min(child_gens)
        self._generations = gen
        return gen

    # ---------- branches ----------

    def branch_of(self, pid: UUID) -> UUID | None:
        """Ancêtre de génération 2 dont la personne descend (ou sa propre branche par alliance)."""
        if self._branch is None:
            gen = self.generations()
            branch: dict[UUID, UUID | None] = {}
            heads = [p for p, g in gen.items() if g == 2 and p in self.persons]
            for h in heads:
                branch.setdefault(h, h)
                for d in self.descendants(h):
                    branch.setdefault(d, h)
            for pid_ in self.persons:
                if pid_ not in branch:
                    for s in self.spouses.get(pid_, ()):
                        if branch.get(s):
                            branch[pid_] = branch[s]
                            break
            self._branch = branch
        return self._branch.get(pid)

    # ---------- titres et préséance ----------

    def active_holdings(self, pid: UUID) -> list[TitleHolding]:
        today = date.today()
        return [
            h
            for h in self.holdings_by_person.get(pid, [])
            if h.ended_on is None or h.ended_on > today
        ]

    def badges(self, pid: UUID) -> list[TitleBadge]:
        today = date.today()
        out = []
        for h in self.holdings_by_person.get(pid, []):
            t = self.titles[h.title_id]
            out.append(
                TitleBadge(
                    holding_id=h.id,
                    title_id=t.id,
                    name=t.name,
                    abbreviation=t.abbreviation,
                    precedence=t.precedence,
                    badge_color=t.badge_color,
                    active=h.ended_on is None or h.ended_on > today,
                )
            )
        out.sort(key=lambda b: (not b.active, b.precedence))
        return out

    def best_title(self, pid: UUID) -> TitleDefinition | None:
        hs = self.active_holdings(pid)
        if not hs:
            return None
        return min((self.titles[h.title_id] for h in hs), key=lambda t: t.precedence)

    def display_name(self, pid: UUID) -> str:
        p = self.persons[pid]
        name = " ".join(x for x in (p.first_name, p.last_name) if x)
        t = self.best_title(pid)
        if t:
            prefix = t.abbreviation or t.name
            return f"{prefix} {name}"
        return name

    def precedence_key(self, pid: UUID) -> tuple:
        """§2.5 : titre le plus élevé → génération → année de naissance → nom."""
        p = self.persons[pid]
        t = self.best_title(pid)
        year = p.birth_year or (p.birth_date.year if p.birth_date else None)
        return (
            t.precedence if t else INF,
            self.generations().get(pid, INF),
            year if year is not None else INF,
            (p.last_name or "").lower(),
            p.first_name.lower(),
        )

    # ---------- représentation ----------

    def summary(self, pid: UUID) -> PersonSummary:
        p = self.persons[pid]
        return PersonSummary(
            id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            traditional_name=p.traditional_name,
            display_name=self.display_name(pid),
            sex=p.sex,
            birth_year=p.birth_year or (p.birth_date.year if p.birth_date else None),
            death_year=p.death_year or (p.death_date.year if p.death_date else None),
            is_living=p.is_living,
            photo_url=p.photo_url,
            generation=self.generations().get(pid),
            titles=self.badges(pid),
            has_account=pid in self.accounts,
        )

    # ---------- périmètre d'écriture (§2.6) ----------

    def writable_scope(self, membership: Membership) -> set[UUID] | None:
        """Personnes que ce membre peut modifier directement ; None = toute la famille.

        - administrateur : toute la famille ;
        - chef de branche : sa personne de branche, ses descendants et leurs conjoints ;
        - autres rôles : sa propre fiche, ses descendants et leurs conjoints ;
        - dans tous les cas, en plus : les personnes qui lui sont déléguées (et leur descendance).
        """
        if membership.role == Role.ADMIN:
            return None
        main = membership.person_id
        if membership.role == Role.BRANCH_HEAD and membership.branch_person_id:
            main = membership.branch_person_id
        anchors = [main, *self.delegations.get(membership.id, ())]
        scope: set[UUID] = set()
        for anchor in anchors:
            if anchor in self.persons:
                scope |= {anchor} | set(self.descendants(anchor))
        for pid in list(scope):
            scope |= self.spouses.get(pid, set())
        if membership.person_id:
            scope.add(membership.person_id)
        return scope

    def can_write(self, membership: Membership, pid: UUID) -> bool:
        scope = self.writable_scope(membership)
        return scope is None or pid in scope

    # ---------- parenté (§2.4) ----------

    def _blood(self, a: UUID, b: UUID) -> tuple[UUID, int, int] | None:
        anc_a = self.ancestors(a)
        anc_a[a] = 0
        anc_b = self.ancestors(b)
        anc_b[b] = 0
        common = set(anc_a) & set(anc_b)
        if not common:
            return None
        best = min(common, key=lambda c: (anc_a[c] + anc_b[c], max(anc_a[c], anc_b[c])))
        return best, anc_a[best], anc_b[best]

    def _path_up(self, start: UUID, target: UUID) -> list[UUID]:
        """Plus court chemin ascendant de start à target (inclus)."""
        prev: dict[UUID, UUID | None] = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if cur == target:
                break
            for par in self.parents.get(cur, ()):
                if par not in prev:
                    prev[par] = cur
                    queue.append(par)
        path = []
        node: UUID | None = target
        while node is not None:
            path.append(node)
            node = prev.get(node)
        return list(reversed(path))  # start → … → target

    def kinship(self, a: UUID, b: UUID) -> dict:
        sex_b = self.persons[b].sex
        if a == b:
            return {"related": True, "label": "vous-même", "relation_type": "self", "path": [a]}

        blood = self._blood(a, b)
        if blood:
            common, da, db_ = blood
            half = False
            if da == 1 and db_ == 1:
                half = len(self.parents.get(a, set()) & self.parents.get(b, set())) == 1
            up = self._path_up(a, common)
            down = list(reversed(self._path_up(b, common)))
            path = up + down[1:]
            return {
                "related": True,
                "label": blood_label(da, db_, sex_b, half),
                "relation_type": "blood",
                "common_ancestor_id": common,
                "distance_from": da,
                "distance_to": db_,
                "path": path,
            }

        if b in self.spouses.get(a, set()):
            return {
                "related": True,
                "label": spouse_label(sex_b),
                "relation_type": "spouse",
                "path": [a, b],
            }

        # B est conjoint d'un parent de sang de A
        for s in self.spouses.get(b, set()):
            blood = self._blood(a, s)
            if blood:
                common, da, ds = blood
                rel = blood_label(da, ds, self.persons[s].sex)
                up = self._path_up(a, common)
                down = list(reversed(self._path_up(s, common)))
                return {
                    "related": True,
                    "label": f"{spouse_label(sex_b)} de votre {rel}",
                    "relation_type": "in_law",
                    "common_ancestor_id": common,
                    "path": up + down[1:] + [b],
                }

        # B est parent de sang du conjoint de A
        for s in self.spouses.get(a, set()):
            blood = self._blood(s, b)
            if blood:
                common, ds, db_ = blood
                rel = blood_label(ds, db_, sex_b)
                up = self._path_up(s, common)
                down = list(reversed(self._path_up(b, common)))
                return {
                    "related": True,
                    "label": f"{rel} de votre {spouse_label(self.persons[s].sex)}",
                    "relation_type": "in_law",
                    "common_ancestor_id": common,
                    "path": [a] + up + down[1:],
                }

        return {"related": False, "label": None, "relation_type": "none", "path": []}


def load_graph(ctx) -> FamilyGraph:  # noqa: ANN001  (FamilyContext, import évité pour rester découplé)
    """Charge le graphe de la famille courante d'une requête."""
    return FamilyGraph.load(ctx.db, ctx.family.id, ctx.family.root_person_id)
