"""Routes des cotisations : barèmes, événements, montants dus, paiements, rapports.

Tous les membres voient les événements et l'état de chacun (transparence) et peuvent
déclarer un paiement. Le trésorier et l'administrateur créent les barèmes et les
événements, ajustent les montants dus, valident les paiements et clôturent.
"""

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import or_, select

from app.core.deps import Ctx, FamilyContext
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.genealogy.graph import FamilyGraph, load_graph
from app.models import (
    ContributionDue,
    ContributionEvent,
    ContributionPayment,
    ContributionScale,
    EventStatus,
    PaymentStatus,
    User,
)
from app.modules.contributions import reports, service
from app.modules.contributions.schemas import (
    DueAdd,
    DueRow,
    DueUpdate,
    EventIn,
    EventOut,
    EventUpdate,
    PaymentIn,
    PaymentOut,
    PersonContribution,
    RecapOut,
    ReviewIn,
    ScaleIn,
    ScaleOut,
    ScaleUpdate,
)
from app.shared import audit, storage
from app.shared.http import attachment
from app.shared.notify import notify

router = APIRouter(prefix="/contributions", tags=["contributions"])


def event_out(ctx: FamilyContext, event: ContributionEvent) -> EventOut:
    out = EventOut.model_validate(event)
    out.totals = service.totals(ctx, event)
    out.can_manage = service.can_manage(ctx)
    return out


# ---------- Barèmes ----------


@router.get("/scales", response_model=list[ScaleOut])
def list_scales(ctx: Ctx) -> list[ContributionScale]:
    return list(
        ctx.db.scalars(
            select(ContributionScale)
            .where(ContributionScale.family_id == ctx.family.id)
            .order_by(ContributionScale.active.desc(), ContributionScale.name)
        )
    )


@router.post("/scales", response_model=ScaleOut, status_code=201)
def create_scale(body: ScaleIn, ctx: Ctx) -> ContributionScale:
    service.require_manager(ctx)
    scale = ContributionScale(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(scale)
    ctx.db.flush()
    audit.record(ctx, "create", "contribution_scale", scale.id, after=audit.snapshot(scale))
    ctx.db.commit()
    return scale


@router.patch("/scales/{scale_id}", response_model=ScaleOut)
def update_scale(scale_id: UUID, body: ScaleUpdate, ctx: Ctx) -> ContributionScale:
    """Modifier un barème n'affecte que les événements créés ensuite (RG-24)."""
    service.require_manager(ctx)
    scale = ctx.db.get(ContributionScale, scale_id)
    if scale is None or scale.family_id != ctx.family.id:
        raise not_found("Barème")
    before = audit.snapshot(scale)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(scale, key, value)
    audit.record(ctx, "update", "contribution_scale", scale.id, before, audit.snapshot(scale))
    ctx.db.commit()
    return scale


# ---------- Événements ----------


@router.get("/events", response_model=list[EventOut])
def list_events(ctx: Ctx, status: Literal["open", "closed", "any"] = "any") -> list[EventOut]:
    query = select(ContributionEvent).where(ContributionEvent.family_id == ctx.family.id)
    if status != "any":
        query = query.where(ContributionEvent.status == status)
    events = ctx.db.scalars(query.order_by(ContributionEvent.created_at.desc()))
    return [event_out(ctx, e) for e in events]


@router.post("/events", response_model=EventOut, status_code=201)
def create_event(body: EventIn, ctx: Ctx) -> EventOut:
    """Crée l'événement et calcule le montant dû de chaque personne selon le barème du jour."""
    service.require_manager(ctx)
    scale = None
    if body.scale_id:
        scale = ctx.db.get(ContributionScale, body.scale_id)
        if scale is None or scale.family_id != ctx.family.id:
            raise not_found("Barème")
    event = ContributionEvent(
        family_id=ctx.family.id,
        created_by=ctx.user.id,
        currency=scale.currency if scale else "XAF",
        scale_snapshot=service.scale_snapshot(scale) if scale else None,
        **body.model_dump(exclude={"scale_id"}),
    )
    ctx.db.add(event)
    ctx.db.flush()
    if scale:
        dues = service.compute_dues(load_graph(ctx), scale, date.today())
        ctx.db.add_all(
            ContributionDue(
                family_id=ctx.family.id, event_id=event.id, person_id=pid, amount=amount
            )
            for pid, amount in dues.items()
        )
    audit.record(ctx, "create", "contribution_event", event.id, after={"title": event.title})
    ctx.db.commit()
    return event_out(ctx, event)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, ctx: Ctx) -> EventOut:
    return event_out(ctx, service.get_event(ctx, event_id))


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(event_id: UUID, body: EventUpdate, ctx: Ctx) -> EventOut:
    service.require_manager(ctx)
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    ctx.db.commit()
    return event_out(ctx, event)


@router.post("/events/{event_id}/close", response_model=EventOut)
def close_event(event_id: UUID, ctx: Ctx) -> EventOut:
    """Clôture définitive (RG-26). Les paiements encore en attente doivent être traités avant."""
    service.require_manager(ctx)
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    if service.paid_by_person(ctx, event.id, PaymentStatus.DECLARED):
        raise bad_request(
            "payments_pending", "Validez ou refusez d'abord les paiements en attente."
        )
    event.status = EventStatus.CLOSED
    event.closed_at = datetime.now(UTC)
    audit.record(ctx, "close", "contribution_event", event.id, after={"title": event.title})
    ctx.db.commit()
    return event_out(ctx, event)


# ---------- Montants dus ----------


@router.get("/events/{event_id}/dues", response_model=list[DueRow])
def list_dues(
    event_id: UUID,
    ctx: Ctx,
    status: Literal["paid", "partial", "unpaid", "exempt", "any"] = "any",
    q: str | None = None,
) -> list[DueRow]:
    """État de chaque personne, dans l'ordre de préséance (transparence : visible par tous)."""
    event = service.get_event(ctx, event_id)
    graph = load_graph(ctx)
    rows = [r for r in service.event_rows(ctx, event) if r.person_id in graph.persons]
    if status != "any":
        rows = [r for r in rows if r.status == status]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in graph.display_name(r.person_id).lower()]
    rows.sort(key=lambda r: graph.precedence_key(r.person_id))
    return [
        DueRow(
            due_id=r.due.id if r.due else None,
            person=graph.summary(r.person_id),
            amount=r.amount,
            paid=r.paid,
            status=r.status,
            exempt=r.due.exempt if r.due else False,
            note=r.due.note if r.due else None,
        )
        for r in rows
    ]


@router.post("/events/{event_id}/dues", status_code=201)
def add_due(event_id: UUID, body: DueAdd, ctx: Ctx) -> dict:
    """Ajouter une personne oubliée par le barème (ex. nouveau membre)."""
    service.require_manager(ctx)
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    if body.person_id not in load_graph(ctx).persons:
        raise not_found("Personne")
    exists = ctx.db.scalar(
        select(ContributionDue).where(
            ContributionDue.event_id == event.id, ContributionDue.person_id == body.person_id
        )
    )
    if exists:
        raise conflict("already_exists", "Cette personne figure déjà dans la liste.")
    due = ContributionDue(family_id=ctx.family.id, event_id=event.id, **body.model_dump())
    ctx.db.add(due)
    ctx.db.flush()
    audit.record(ctx, "create", "contribution_due", due.id, after=audit.snapshot(due))
    ctx.db.commit()
    return {"id": str(due.id)}


@router.patch("/dues/{due_id}", status_code=204)
def update_due(due_id: UUID, body: DueUpdate, ctx: Ctx) -> None:
    """Ajuster un montant ou exempter une personne, avec une note (ex. « étudiant »)."""
    service.require_manager(ctx)
    due = ctx.db.get(ContributionDue, due_id)
    if due is None or due.family_id != ctx.family.id:
        raise not_found("Montant dû")
    service.require_open(service.get_event(ctx, due.event_id))
    before = audit.snapshot(due)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(due, key, value)
    audit.record(ctx, "update", "contribution_due", due.id, before, audit.snapshot(due))
    ctx.db.commit()


# ---------- Paiements ----------


def payment_out(
    p: ContributionPayment, graph: FamilyGraph, names: dict, show_proof: bool
) -> PaymentOut:
    out = PaymentOut.model_validate(p)
    out.person = graph.summary(p.person_id) if p.person_id in graph.persons else None
    out.declared_by_name = names.get(p.declared_by)
    if not show_proof:
        out.proof_url = None
    return out


@router.get("/events/{event_id}/payments", response_model=list[PaymentOut])
def list_payments(
    event_id: UUID,
    ctx: Ctx,
    status: Literal["declared", "validated", "rejected", "any"] = "any",
    mine: bool = False,
) -> list[PaymentOut]:
    """Le trésorier voit tout ; un membre voit ses déclarations et les paiements validés."""
    service.get_event(ctx, event_id)
    query = select(ContributionPayment).where(ContributionPayment.event_id == event_id)
    if status != "any":
        query = query.where(ContributionPayment.status == status)
    if mine:
        query = query.where(ContributionPayment.declared_by == ctx.user.id)
    elif not service.can_manage(ctx):
        query = query.where(
            or_(
                ContributionPayment.declared_by == ctx.user.id,
                ContributionPayment.status == PaymentStatus.VALIDATED,
            )
        )
    payments = list(ctx.db.scalars(query.order_by(ContributionPayment.created_at.desc())))
    graph = load_graph(ctx)
    ids = {p.declared_by for p in payments}
    names = (
        {u.id: u.full_name for u in ctx.db.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    manager = service.can_manage(ctx)
    return [payment_out(p, graph, names, manager or p.declared_by == ctx.user.id) for p in payments]


@router.post("/events/{event_id}/payments", response_model=PaymentOut, status_code=201)
def declare_payment(event_id: UUID, body: PaymentIn, ctx: Ctx) -> PaymentOut:
    """Tout membre déclare un paiement, pour lui ou pour un proche (RG-25).
    Déclaré par le trésorier (ex. espèces reçues en main propre), il est validé d'office."""
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    graph = load_graph(ctx)
    if body.person_id not in graph.persons:
        raise not_found("Personne")
    manager = service.can_manage(ctx)
    payment = ContributionPayment(
        family_id=ctx.family.id,
        event_id=event.id,
        declared_by=ctx.user.id,
        status=PaymentStatus.VALIDATED if manager else PaymentStatus.DECLARED,
        reviewed_by=ctx.user.id if manager else None,
        reviewed_at=datetime.now(UTC) if manager else None,
        **body.model_dump(),
    )
    ctx.db.add(payment)
    ctx.db.flush()
    audit.record(ctx, "create", "contribution_payment", payment.id, after=audit.snapshot(payment))
    ctx.db.commit()
    return payment_out(payment, graph, {ctx.user.id: ctx.user.full_name}, True)


def get_payment(ctx: FamilyContext, payment_id: UUID) -> ContributionPayment:
    # Verrou de ligne : un paiement n'est validé qu'une fois, même par deux trésoriers à la fois
    payment = ctx.db.get(ContributionPayment, payment_id, with_for_update=True)
    if payment is None or payment.family_id != ctx.family.id:
        raise not_found("Paiement")
    return payment


@router.post("/payments/{payment_id}/proof", response_model=PaymentOut)
async def upload_proof(payment_id: UUID, ctx: Ctx, file: UploadFile = File(...)) -> PaymentOut:
    """Joindre la capture du reçu (Mobile Money, virement…)."""
    payment = get_payment(ctx, payment_id)
    if payment.declared_by != ctx.user.id and not service.can_manage(ctx):
        raise forbidden("Seul l'auteur de la déclaration peut joindre un reçu.")
    payment.proof_url = storage.save_photo(ctx.family.id, await file.read())
    ctx.db.commit()
    return payment_out(payment, load_graph(ctx), {}, True)


def review(ctx: FamilyContext, payment_id: UUID, status: str, body: ReviewIn) -> PaymentOut:
    service.require_manager(ctx)
    payment = get_payment(ctx, payment_id)
    service.require_open(service.get_event(ctx, payment.event_id))
    if payment.status != PaymentStatus.DECLARED:
        raise bad_request("already_reviewed", "Ce paiement a déjà été traité.")
    before = audit.snapshot(payment)
    if body.amount and status == PaymentStatus.VALIDATED:
        payment.amount = body.amount
    payment.status = status
    payment.review_note = body.note
    payment.reviewed_by = ctx.user.id
    payment.reviewed_at = datetime.now(UTC)
    audit.record(ctx, status, "contribution_payment", payment.id, before, audit.snapshot(payment))
    validated = status == PaymentStatus.VALIDATED
    notify(
        ctx,
        [payment.declared_by],
        "payment_validated" if validated else "payment_rejected",
        f"Paiement {'validé' if validated else 'refusé'} par le trésorier",
        link=f"/cotisations/{payment.event_id}",
        body=body.note,
    )
    ctx.db.commit()
    return payment_out(payment, load_graph(ctx), {}, True)


@router.post("/payments/{payment_id}/validate", response_model=PaymentOut)
def validate_payment(payment_id: UUID, body: ReviewIn, ctx: Ctx) -> PaymentOut:
    return review(ctx, payment_id, PaymentStatus.VALIDATED, body)


@router.post("/payments/{payment_id}/reject", response_model=PaymentOut)
def reject_payment(payment_id: UUID, body: ReviewIn, ctx: Ctx) -> PaymentOut:
    if not (body.note and body.note.strip()):
        raise bad_request("note_required", "Indiquez le motif du refus.")
    return review(ctx, payment_id, PaymentStatus.REJECTED, body)


# ---------- Rapports et historique ----------


@router.get("/events/{event_id}/recap", response_model=RecapOut)
def recap(event_id: UUID, ctx: Ctx, only_unpaid: bool = False) -> RecapOut:
    event = service.get_event(ctx, event_id)
    rows = service.event_rows(ctx, event)
    text = reports.recap_text(event, service.totals(ctx, event), rows, load_graph(ctx), only_unpaid)
    return RecapOut(text=text)


@router.get("/events/{event_id}/export.csv", response_class=PlainTextResponse)
def export_csv(event_id: UUID, ctx: Ctx) -> PlainTextResponse:
    event = service.get_event(ctx, event_id)
    content = reports.csv_export(event, service.event_rows(ctx, event), load_graph(ctx))
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": attachment(f"{event.title}.csv")},
    )


@router.get("/persons/{person_id}", response_model=list[PersonContribution])
def person_history(person_id: UUID, ctx: Ctx) -> list[PersonContribution]:
    """Historique permanent d'une personne : chaque événement, son dû et ce qu'elle a payé."""
    if person_id not in load_graph(ctx).persons:
        raise not_found("Personne")
    events = ctx.db.scalars(
        select(ContributionEvent)
        .where(ContributionEvent.family_id == ctx.family.id)
        .order_by(ContributionEvent.created_at.desc())
    )
    history = []
    for event in events:
        row = next((r for r in service.event_rows(ctx, event) if r.person_id == person_id), None)
        if row:
            history.append(
                PersonContribution(
                    event=event_out(ctx, event), amount=row.amount, paid=row.paid, status=row.status
                )
            )
    return history
