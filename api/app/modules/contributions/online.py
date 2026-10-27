"""Cotisations, phase 6 : rappels personnalisés par WhatsApp et paiement Mobile Money en ligne.

- Rappels : pour chaque personne qui n'a pas tout payé, un message avec sa part, ce qu'elle a
  déjà versé et ce qui reste. Selon la configuration, il part directement (API WhatsApp
  Business) ou il est préparé en lien wa.me que le trésorier ouvre (gratuit).
- Paiement en ligne : le membre lance le paiement ; le prestataire confirme par webhook ;
  le paiement passe alors en « validé » sans intervention du trésorier.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import set_family_context
from app.core.deps import DB, Ctx
from app.core.errors import AppError, bad_request, not_found
from app.genealogy.graph import FamilyGraph, load_graph
from app.integrations.messaging import get_messenger
from app.integrations.payments import InvalidSignatureError, get_gateway
from app.models import (
    ContributionEvent,
    ContributionPayment,
    Membership,
    Notification,
    PaymentIntent,
    PaymentStatus,
    User,
)
from app.modules.contributions import service
from app.modules.contributions.reports import money
from app.modules.persons.schemas import PersonSummary
from app.security import events, ratelimit
from app.shared import audit

router = APIRouter(tags=["contributions"])


# ---------- Rappels ----------


class ReminderIn(BaseModel):
    person_ids: list[UUID] | None = None  # aucune liste : toutes les personnes en retard
    note: str | None = Field(default=None, max_length=300)  # ex. numéro Mobile Money du trésorier


class ReminderOut(BaseModel):
    person: PersonSummary
    phone: str | None
    text: str
    status: str  # to_share | sent | failed | no_phone
    link: str | None


class RemindersOut(BaseModel):
    backend: str
    items: list[ReminderOut]


def reachable_phone(ctx: Ctx, graph: FamilyGraph, pid: UUID) -> str | None:
    """Le numéro de la personne, sinon celui de son compte, sinon celui de son délégué
    (un ancien sans téléphone est joint par la personne qui gère sa fiche)."""
    person = graph.persons[pid]
    if person.phone:
        return person.phone
    user_id = graph.accounts.get(pid)
    if user_id:
        user = ctx.db.get(User, user_id)
        if user and user.phone:
            return user.phone
    for membership_id, persons in graph.delegations.items():
        if pid in persons:
            m = ctx.db.get(Membership, membership_id)
            delegate = graph.persons.get(m.person_id) if m and m.person_id else None
            if delegate and delegate.phone:
                return delegate.phone
    return None


@router.post("/contributions/events/{event_id}/reminders", response_model=RemindersOut)
def send_reminders(event_id: UUID, body: ReminderIn, ctx: Ctx) -> RemindersOut:
    service.require_manager(ctx)
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    graph = load_graph(ctx)
    messenger = get_messenger()
    wanted = set(body.person_ids) if body.person_ids is not None else None
    items = []
    for row in service.event_rows(ctx, event):
        if row.status not in ("unpaid", "partial") or row.person_id not in graph.persons:
            continue
        if wanted is not None and row.person_id not in wanted:
            continue
        p = graph.persons[row.person_id]
        lines = [
            f"Bonjour {p.first_name},",
            f"pour « {event.title} », la part de {graph.display_name(p.id)} est de {money(row.amount, event.currency)}.",
        ]
        if row.paid:
            lines.append(
                f"Déjà versé : {money(row.paid, event.currency)}. Reste : {money(row.amount - row.paid, event.currency)}."
            )
        if event.deadline:
            lines.append(f"Date limite : {event.deadline.strftime('%d/%m/%Y')}.")
        if body.note:
            lines.append(body.note)
        lines.append("Merci, et déclarez votre paiement sur Sheenu une fois fait.")
        text = "\n".join(lines)
        phone = reachable_phone(ctx, graph, p.id)
        delivery = messenger.send(phone, text)
        items.append(
            ReminderOut(
                person=graph.summary(p.id),
                phone=phone,
                text=text,
                status=delivery.status,
                link=delivery.link,
            )
        )
    items.sort(key=lambda i: i.status == "no_phone")  # les personnes joignables d'abord
    audit.record(ctx, "remind", "contribution_event", event.id, after={"count": len(items)})
    ctx.db.commit()
    return RemindersOut(backend=messenger.name, items=items)


# ---------- Paiement en ligne ----------


class PayOnlineIn(BaseModel):
    person_id: UUID
    amount: int = Field(gt=0)
    phone: str = Field(min_length=6, max_length=32)


class PayOnlineOut(BaseModel):
    payment_id: UUID
    provider: str
    reference: str
    instructions: str


class OnlineStatus(BaseModel):
    enabled: bool
    provider: str | None


@router.get("/contributions/online", response_model=OnlineStatus)
def online_status(ctx: Ctx) -> OnlineStatus:
    gateway = get_gateway()
    return OnlineStatus(enabled=gateway is not None, provider=gateway.name if gateway else None)


@router.post(
    "/contributions/events/{event_id}/pay-online", response_model=PayOnlineOut, status_code=201
)
def pay_online(event_id: UUID, body: PayOnlineIn, ctx: Ctx) -> PayOnlineOut:
    gateway = get_gateway()
    if gateway is None:
        raise bad_request(
            "online_disabled", "Le paiement en ligne n'est pas activé pour cette famille."
        )
    event = service.get_event(ctx, event_id)
    service.require_open(event)
    graph = load_graph(ctx)
    if body.person_id not in graph.persons:
        raise not_found("Personne")
    checkout = gateway.start(amount=body.amount, phone=body.phone, description=event.title)
    payment = ContributionPayment(
        family_id=ctx.family.id,
        event_id=event.id,
        person_id=body.person_id,
        amount=body.amount,
        method="mobile_money",
        reference=checkout.provider_ref,
        declared_by=ctx.user.id,
        status=PaymentStatus.DECLARED,
    )
    ctx.db.add(payment)
    ctx.db.flush()
    ctx.db.add(
        PaymentIntent(
            family_id=ctx.family.id,
            payment_id=payment.id,
            provider=gateway.name,
            provider_ref=checkout.provider_ref,
            amount=body.amount,
        )
    )
    audit.record(ctx, "create", "contribution_payment", payment.id, after={"online": gateway.name})
    ctx.db.commit()
    return PayOnlineOut(
        payment_id=payment.id,
        provider=gateway.name,
        reference=checkout.provider_ref,
        instructions=checkout.instructions,
    )


@router.post("/webhooks/payments/{provider}", status_code=204)
async def payment_webhook(
    provider: str, request: Request, db: DB, x_signature: str | None = Header(default=None)
) -> None:
    """Confirmation du prestataire. Sans compte ni famille : on retrouve le paiement par sa
    référence (table hors RLS), puis on ouvre le contexte de sa famille pour le mettre à jour."""
    gateway = get_gateway()
    if gateway is None or gateway.name != provider:
        raise not_found("Prestataire")
    ratelimit.enforce("webhook", events.client_ip(request) or "?", request)
    try:
        event = gateway.parse_webhook(await request.body(), x_signature)
    except (InvalidSignatureError, ValueError, KeyError) as exc:
        # Webhook forgé ou altéré : on refuse et on alerte la supervision
        events.record("bad_signature", request, provider=provider)
        raise AppError(401, "invalid_signature", "Signature invalide.") from exc
    intent = db.scalar(
        select(PaymentIntent).where(
            PaymentIntent.provider == provider, PaymentIntent.provider_ref == event.provider_ref
        )
    )
    if intent is None:
        raise not_found("Paiement")
    if intent.status != "pending":  # les prestataires renvoient parfois deux fois : sans effet
        return
    intent.status = "success" if event.success else "failed"
    intent.completed_at = datetime.now(UTC)
    set_family_context(db, intent.family_id)
    payment = db.get(ContributionPayment, intent.payment_id)
    if payment and payment.status == PaymentStatus.DECLARED:
        payment.status = PaymentStatus.VALIDATED if event.success else PaymentStatus.REJECTED
        payment.reviewed_at = datetime.now(UTC)
        payment.review_note = (
            f"Confirmé par {provider}" if event.success else f"Échec chez {provider}"
        )
        # Le prestataire n'est pas un membre : la notification est écrite directement
        currency = db.get(ContributionEvent, payment.event_id).currency
        verb = "confirmé" if event.success else "échoué"
        db.add(
            Notification(
                family_id=intent.family_id,
                user_id=payment.declared_by,
                kind="payment_validated" if event.success else "payment_rejected",
                title=f"Paiement en ligne de {money(payment.amount, currency)} {verb}",
                link=f"/cotisations/{payment.event_id}",
            )
        )
    db.commit()
