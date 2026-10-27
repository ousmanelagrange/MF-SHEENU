"""Création des notifications, appelée par les modules au moment où l'événement se produit
(dans la même transaction : si l'action échoue, la notification disparaît avec elle)."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.models import Membership, Notification


def notify(
    ctx: FamilyContext,
    user_ids: Iterable[UUID | None],
    kind: str,
    title: str,
    link: str | None = None,
    body: str | None = None,
) -> None:
    """Notifie des membres de la famille courante. L'auteur de l'action n'est jamais notifié."""
    targets = {u for u in user_ids if u and u != ctx.user.id}
    ctx.db.add_all(
        Notification(
            family_id=ctx.family.id, user_id=u, kind=kind, title=title[:200], link=link, body=body
        )
        for u in targets
    )


def members(ctx: FamilyContext, roles: tuple[str, ...] | None = None) -> list[UUID]:
    """Comptes membres de la famille courante, éventuellement limités à certains rôles."""
    query = select(Membership.user_id).where(Membership.family_id == ctx.family.id)
    if roles:
        query = query.where(Membership.role.in_(roles))
    return list(ctx.db.scalars(query))
