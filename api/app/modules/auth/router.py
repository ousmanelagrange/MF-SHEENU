"""Routes d'authentification : inscription, connexion, sessions, mot de passe, profil.

Un compte se connecte avec son e-mail ou son téléphone. Chaque connexion ouvre une session
d'appareil. Le jeton d'accès dure 30 minutes ; le jeton de rafraîchissement en obtient un
nouveau et change à chaque usage (rotation). Protections :

- limite de débit par adresse IP sur la connexion, l'inscription et le rafraîchissement ;
- verrouillage du compte après 5 échecs (15 minutes, puis de plus en plus long) ;
- même temps de réponse qu'un compte existe ou non ;
- un ancien jeton de rafraîchissement présenté à nouveau trahit un vol : toutes les
  sessions du compte sont fermées et l'événement est signalé à la supervision.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select, update

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser, bearer
from app.core.errors import AppError, bad_request, conflict, not_found
from app.core.security import (
    DUMMY_HASH,
    create_session_tokens,
    decode_token,
    hash_password,
    verify_password,
    weak_password,
)
from app.models import AuthSession, User
from app.modules.auth.schemas import (
    LoginIn,
    PasswordIn,
    RefreshIn,
    RegisterIn,
    SessionOut,
    TokenOut,
    UserOut,
    UserUpdate,
)
from app.security import events, ratelimit

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILURES = 5
RACE_GRACE = timedelta(seconds=30)  # deux rafraîchissements simultanés d'un même appareil


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    return digits or None


def open_session(db, user: User, request: Request) -> TokenOut:  # noqa: ANN001
    session = AuthSession(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        ip=events.client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(session)
    db.flush()
    access, refresh = create_session_tokens(user.id, user.token_version, session.id, 0)
    return TokenOut(access_token=access, refresh_token=refresh)


def revoke_all(db, user: User, reason: str) -> None:  # noqa: ANN001
    """Ferme toutes les sessions et invalide tous les jetons d'accès du compte."""
    user.token_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=201,
    dependencies=[Depends(ratelimit.limit("register"))],
)
def register(body: RegisterIn, request: Request, db: DB) -> TokenOut:
    email = body.email.lower() if body.email else None
    phone = normalize_phone(body.phone)
    reason = weak_password(body.password, email, body.full_name, phone)
    if reason:
        raise bad_request("weak_password", reason)
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
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    tokens = open_session(db, user, request)
    db.commit()
    return tokens


@router.post("/login", response_model=TokenOut, dependencies=[Depends(ratelimit.limit("login"))])
def login(body: LoginIn, request: Request, db: DB) -> TokenOut:
    ident = body.login.strip()
    if "@" in ident:
        user = db.scalar(select(User).where(User.email == ident.lower()))
    else:
        user = db.scalar(select(User).where(User.phone == normalize_phone(ident)))
    now = datetime.now(UTC)
    # Toujours une vérification bcrypt, même sans compte : même durée dans tous les cas
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)

    if user and user.locked_until and user.locked_until > now:
        minutes = int((user.locked_until - now).total_seconds() // 60) + 1
        events.record("login_locked", request, user.id)
        raise AppError(
            429, "account_locked", f"Trop d'essais. Compte verrouillé encore {minutes} min."
        )
    if user is None or not user.is_active or not valid:
        if user is not None and user.is_active:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILURES:
                # 15 min, puis 30, 60… jusqu'à 4 heures
                factor = 2 ** min(user.failed_logins - MAX_FAILURES, 4)
                user.locked_until = now + timedelta(minutes=15 * factor)
                events.record("login_locked", request, user.id, failures=user.failed_logins)
            db.commit()
        events.record("login_failed", request, user.id if user else None, login=ident[:3] + "…")
        raise AppError(401, "invalid_credentials", "Identifiant ou mot de passe incorrect.")

    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now
    tokens = open_session(db, user, request)
    db.commit()
    events.record("login", request, user.id)
    return tokens


@router.post(
    "/refresh", response_model=TokenOut, dependencies=[Depends(ratelimit.limit("refresh"))]
)
def refresh(body: RefreshIn, request: Request, db: DB) -> TokenOut:
    expired = AppError(401, "not_authenticated", "Session expirée, reconnectez-vous.")
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError as exc:
        raise expired from exc
    if payload.get("typ") != "refresh" or "sid" not in payload:
        raise expired
    session = db.get(AuthSession, UUID(payload["sid"]))
    user = db.get(User, UUID(payload["sub"]))
    now = datetime.now(UTC)
    if session is None or user is None or session.user_id != user.id:
        raise expired
    if (
        session.revoked_at
        or session.expires_at < now
        or not user.is_active
        or user.token_version != payload.get("ver")
    ):
        raise expired

    rot = payload.get("rot", -1)
    if rot != session.rotation:
        benign = rot == session.rotation - 1 and now - session.last_used_at < RACE_GRACE
        if not benign:
            # Un jeton déjà remplacé revient : il a été copié. On ferme tout.
            revoke_all(db, user, "refresh_reuse")
            db.commit()
            events.record("refresh_reuse", request, user.id, session=session.id)
            raise AppError(401, "session_revoked", "Session fermée par sécurité. Reconnectez-vous.")
    else:
        session.rotation += 1
    session.last_used_at = now
    access, refresh_token = create_session_tokens(
        user.id, user.token_version, session.id, session.rotation
    )
    db.commit()
    return TokenOut(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: DB) -> None:
    """Ferme la session de cet appareil."""
    try:
        payload = decode_token(body.refresh_token)
        session = db.get(AuthSession, UUID(payload["sid"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return
    if session and session.revoked_at is None:
        session.revoked_at, session.revoked_reason = datetime.now(UTC), "logout"
        db.commit()


@router.post("/logout-all", status_code=204)
def logout_all(user: CurrentUser, db: DB) -> None:
    revoke_all(db, user, "logout_all")
    db.commit()


@router.post(
    "/password", response_model=TokenOut, dependencies=[Depends(ratelimit.limit("password"))]
)
def change_password(body: PasswordIn, request: Request, user: CurrentUser, db: DB) -> TokenOut:
    """Changer de mot de passe ferme toutes les autres sessions (un intrus éventuel est éjecté)."""
    if not verify_password(body.current_password, user.password_hash):
        events.record("login_failed", request, user.id, during="password_change")
        raise AppError(403, "invalid_credentials", "Mot de passe actuel incorrect.")
    reason = weak_password(body.new_password, user.email, user.full_name, user.phone)
    if reason:
        raise bad_request("weak_password", reason)
    user.password_hash = hash_password(body.new_password)
    revoke_all(db, user, "password_changed")
    tokens = open_session(db, user, request)
    db.commit()
    events.record("password_changed", request, user.id)
    return tokens


def _current_sid(creds: HTTPAuthorizationCredentials | None) -> str | None:
    try:
        return decode_token(creds.credentials).get("sid") if creds else None
    except jwt.PyJWTError:
        return None


@router.get("/sessions", response_model=list[SessionOut])
def sessions(
    user: CurrentUser, db: DB, creds: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> list[SessionOut]:
    """Les appareils connectés au compte."""
    sid = _current_sid(creds)
    rows = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
        .order_by(AuthSession.last_used_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            ip=s.ip,
            user_agent=s.user_agent,
            current=str(s.id) == sid,
        )
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def close_session(session_id: UUID, user: CurrentUser, db: DB) -> None:
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user.id:
        raise not_found("Session")
    session.revoked_at, session.revoked_reason = datetime.now(UTC), "closed_by_user"
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
