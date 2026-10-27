"""Dépendances FastAPI : utilisateur courant, famille courante, rôles."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_family_context
from app.core.errors import AppError, forbidden
from app.core.security import decode_token
from app.models import Family, Membership, Role, User

bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if creds is None:
        raise AppError(401, "not_authenticated", "Authentification requise.")
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Session expirée.") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "not_authenticated", "Jeton invalide.") from exc
    if payload.get("typ") != "access":
        raise AppError(401, "not_authenticated", "Jeton invalide.")
    user = db.get(User, UUID(payload["sub"]))
    if user is None or not user.is_active or user.token_version != payload.get("ver"):
        raise AppError(401, "not_authenticated", "Session révoquée.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class FamilyContext:
    db: Session
    user: User
    family: Family
    membership: Membership

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def is_admin(self) -> bool:
        return self.membership.role == Role.ADMIN

    @property
    def is_board(self) -> bool:
        return self.membership.role in (Role.ADMIN, Role.TREASURER, Role.SECRETARY)


def get_family_context(
    db: DB,
    user: CurrentUser,
    x_family_id: Annotated[UUID | None, Header()] = None,
) -> FamilyContext:
    if x_family_id is None:
        raise AppError(400, "family_required", "En-tête X-Family-Id manquant.")
    membership = db.scalar(
        select(Membership).where(
            Membership.family_id == x_family_id,
            Membership.user_id == user.id,
            Membership.status == "active",
        )
    )
    if membership is None:
        raise AppError(403, "not_a_member", "Vous n'êtes pas membre de cette famille.")
    family = db.get(Family, x_family_id)
    set_family_context(db, family.id)
    return FamilyContext(db=db, user=user, family=family, membership=membership)


Ctx = Annotated[FamilyContext, Depends(get_family_context)]


def require_roles(*roles: str):
    def checker(ctx: Ctx) -> FamilyContext:
        if ctx.role not in roles:
            raise forbidden("Votre rôle ne permet pas cette action.")
        return ctx

    return Depends(checker)


AdminCtx = Annotated[FamilyContext, require_roles(Role.ADMIN)]
InviterCtx = Annotated[FamilyContext, require_roles(Role.ADMIN, Role.BRANCH_HEAD)]
