"""Routes d'authentification : inscription, connexion, jetons, profil du compte.

Un compte se connecte avec son e-mail ou son téléphone. Les jetons d'accès durent
30 minutes ; le jeton de rafraîchissement permet d'en obtenir un nouveau sans ressaisir
le mot de passe. « Se déconnecter partout » invalide tous les jetons existants.
"""

from uuid import UUID

import jwt
from fastapi import APIRouter
from sqlalchemy import or_, select

from app.core.deps import DB, CurrentUser
from app.core.errors import AppError, conflict
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.modules.auth.schemas import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    return digits or None


def _tokens(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=create_refresh_token(user.id, user.token_version),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: DB) -> TokenOut:
    email = body.email.lower() if body.email else None
    phone = normalize_phone(body.phone)
    clauses = []
    if email:
        clauses.append(User.email == email)
    if phone:
        clauses.append(User.phone == phone)
    if db.scalar(select(User).where(or_(*clauses))):
        raise conflict("already_exists", "Un compte existe déjà avec cet e-mail ou ce numéro.")
    user = User(
        email=email,
        phone=phone,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        locale=body.locale,
    )
    db.add(user)
    db.commit()
    return _tokens(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DB) -> TokenOut:
    ident = body.login.strip()
    if "@" in ident:
        user = db.scalar(select(User).where(User.email == ident.lower()))
    else:
        user = db.scalar(select(User).where(User.phone == normalize_phone(ident)))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Identifiant ou mot de passe incorrect.")
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: DB) -> TokenOut:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "not_authenticated", "Session expirée, reconnectez-vous.") from exc
    if payload.get("typ") != "refresh":
        raise AppError(401, "not_authenticated", "Jeton invalide.")
    user = db.get(User, UUID(payload["sub"]))
    if user is None or not user.is_active or user.token_version != payload.get("ver"):
        raise AppError(401, "not_authenticated", "Session révoquée.")
    return _tokens(user)


@router.post("/logout-all", status_code=204)
def logout_all(user: CurrentUser, db: DB) -> None:
    user.token_version += 1
    db.add(user)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUser, db: DB) -> User:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    return user
