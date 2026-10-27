"""Règles des cotisations : calcul des montants dus, état de chaque personne, totaux.

Principe (RG-23 à RG-26) :
- un barème donne un montant par génération ;
- à la création d'un événement, on fige ce barème et on calcule le dû de chaque personne
  vivante concernée ; le trésorier peut ensuite ajuster au cas par cas ;
- seuls les paiements validés comptent ; un événement clôturé ne se modifie plus.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import bad_request, forbidden, not_found
from app.genealogy.graph import FamilyGraph
from app.models import (
    ContributionDue,
    ContributionEvent,
    ContributionPayment,
    ContributionScale,
    EventStatus,
    PaymentStatus,
    Role,
)
from app.modules.contributions.schemas import Totals

MANAGER_ROLES = (Role.ADMIN, Role.TREASURER)


def can_manage(ctx: FamilyContext) -> bool:
    """Le trésorier et l'administrateur gèrent les cotisations."""
    return ctx.role in MANAGER_ROLES


def require_manager(ctx: FamilyContext) -> None:
    if not can_manage(ctx):
        raise forbidden("Réservé au trésorier et au bureau.")


def get_event(ctx: FamilyContext, event_id: UUID) -> ContributionEvent:
    event = ctx.db.get(ContributionEvent, event_id)
    if event is None or event.family_id != ctx.family.id:
        raise not_found("Événement")
    return event


def require_open(event: ContributionEvent) -> None:
    """RG-26 : après clôture, l'historique est définitif."""
    if event.status != EventStatus.OPEN:
        raise bad_request(
            "event_closed", "Cet événement est clôturé : il ne peut plus être modifié."
        )


# ---------- Calcul des montants dus ----------


def is_by_alliance(graph: FamilyGraph, pid: UUID) -> bool:
    """Conjoint entré par mariage : aucun parent dans l'arbre, au moins une union,
    et ni la racine ni un de ses ascendants."""
    if graph.parents.get(pid) or not graph.spouses.get(pid):
        return False
    root = graph.root_id
    return not (root and (pid == root or pid in graph.ancestors(root)))


def age_on(p, on: date) -> int | None:  # noqa: ANN001
    if p.birth_date:
        b = p.birth_date
        return on.year - b.year - ((on.month, on.day) < (b.month, b.day))
    if p.birth_year:
        return on.year - p.birth_year
    return None  # âge inconnu : la personne n'est pas exemptée


def compute_dues(graph: FamilyGraph, scale: ContributionScale, on: date) -> dict[UUID, int]:
    """Montant dû par chaque personne vivante selon le barème, à la date donnée."""
    generations = graph.generations()
    dues: dict[UUID, int] = {}
    for pid, p in graph.persons.items():
        if not p.is_living:
            continue
        if not scale.include_spouses and is_by_alliance(graph, pid):
            continue
        if scale.exempt_under_age is not None:
            age = age_on(p, on)
            if age is not None and age < scale.exempt_under_age:
                continue
        gen = generations.get(pid)
        amount = (
            scale.amounts_by_generation.get(str(gen), scale.default_amount)
            if gen
            else scale.default_amount
        )
        if amount > 0:
            dues[pid] = amount
    return dues


def scale_snapshot(scale: ContributionScale) -> dict:
    return {
        "name": scale.name,
        "currency": scale.currency,
        "amounts_by_generation": scale.amounts_by_generation,
        "default_amount": scale.default_amount,
        "exempt_under_age": scale.exempt_under_age,
        "include_spouses": scale.include_spouses,
    }


# ---------- État d'un événement ----------


def paid_by_person(
    ctx: FamilyContext, event_id: UUID, status: str = PaymentStatus.VALIDATED
) -> dict[UUID, int]:
    totals: dict[UUID, int] = defaultdict(int)
    for pay in ctx.db.scalars(
        select(ContributionPayment).where(
            ContributionPayment.event_id == event_id, ContributionPayment.status == status
        )
    ):
        totals[pay.person_id] += pay.amount
    return totals


def due_status(amount: int, paid: int, exempt: bool) -> str:
    if exempt or amount == 0:
        return "exempt"
    if paid >= amount:
        return "paid"
    return "partial" if paid > 0 else "unpaid"


@dataclass
class Row:
    """Situation d'une personne pour un événement."""

    due: ContributionDue | None  # None : paiement spontané, sans montant dû
    person_id: UUID
    amount: int
    paid: int
    status: str


def event_rows(ctx: FamilyContext, event: ContributionEvent) -> list[Row]:
    dues = list(ctx.db.scalars(select(ContributionDue).where(ContributionDue.event_id == event.id)))
    paid = paid_by_person(ctx, event.id)
    rows = [
        Row(
            d,
            d.person_id,
            d.amount,
            paid.get(d.person_id, 0),
            due_status(d.amount, paid.get(d.person_id, 0), d.exempt),
        )
        for d in dues
    ]
    with_due = {d.person_id for d in dues}
    rows += [
        Row(None, pid, 0, amount, "paid") for pid, amount in paid.items() if pid not in with_due
    ]
    return rows


def totals(ctx: FamilyContext, event: ContributionEvent) -> Totals:
    rows = event_rows(ctx, event)
    counted = [r for r in rows if r.due and r.status != "exempt"]
    return Totals(
        due=sum(r.amount for r in counted),
        collected=sum(r.paid for r in rows),
        pending=sum(paid_by_person(ctx, event.id, PaymentStatus.DECLARED).values()),
        persons_due=len(counted),
        paid=sum(1 for r in counted if r.status == "paid"),
        partial=sum(1 for r in counted if r.status == "partial"),
        unpaid=sum(1 for r in counted if r.status == "unpaid"),
        exempt=sum(1 for r in rows if r.status == "exempt"),
    )
