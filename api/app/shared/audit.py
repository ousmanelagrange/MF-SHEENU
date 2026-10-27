"""Écriture du journal d'audit (RG-15) : qui, quoi, quand, valeurs avant et après."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import inspect

from app.core.deps import FamilyContext
from app.models import AuditLog

_SKIP = {"password_hash", "token_hash"}


def snapshot(obj) -> dict:  # noqa: ANN001
    data = {}
    for attr in inspect(obj).mapper.column_attrs:
        key = attr.key
        if key in _SKIP:
            continue
        value = getattr(obj, key)
        if isinstance(value, UUID):
            value = str(value)
        elif isinstance(value, (date, datetime)):
            value = value.isoformat()
        data[key] = value
    return data


def record(
    ctx: FamilyContext,
    action: str,
    entity: str,
    entity_id: UUID | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Ajoute une ligne au journal d'audit (RG-15) dans la transaction en cours."""
    if before and after:
        changed = {k for k in after if before.get(k) != after.get(k)}
        before = {k: v for k, v in before.items() if k in changed}
        after = {k: v for k, v in after.items() if k in changed}
    ctx.db.add(
        AuditLog(
            family_id=ctx.family.id,
            user_id=ctx.user.id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
