"""Mots de passe (bcrypt), jetons JWT et jetons d'invitation."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _create_token(user_id: UUID, token_version: int, kind: str, lifetime: timedelta) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "typ": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: UUID, token_version: int) -> str:
    return _create_token(
        user_id, token_version, "access", timedelta(minutes=get_settings().access_token_minutes)
    )


def create_refresh_token(user_id: UUID, token_version: int) -> str:
    return _create_token(
        user_id, token_version, "refresh", timedelta(days=get_settings().refresh_token_days)
    )


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])


def new_invitation_token() -> tuple[str, str]:
    """Renvoie (jeton clair, empreinte SHA-256). Seule l'empreinte est stockée."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- Robustesse des mots de passe ----------

# Les mots de passe les plus utilisés (listes publiques de fuites), en minuscules
COMMON = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "motdepasse",
    "azertyuiop",
    "qwertyuiop",
    "azerty123",
    "qwerty123",
    "iloveyou",
    "11111111",
    "00000000",
    "88888888",
    "abcd1234",
    "abc12345",
    "12341234",
    "87654321",
    "sunshine",
    "princess",
    "football",
    "baseball",
    "welcome1",
    "admin123",
    "letmein1",
    "cameroun",
    "cameroon",
    "bonjour1",
    "famille1",
    "sheenu123",
    "passw0rd",
    "p@ssw0rd",
    "trustno1",
    "dragon12",
    "monkey12",
}

# Une empreinte réelle d'un mot de passe aléatoire : la vérifier quand le compte n'existe
# pas prend le même temps qu'une vraie vérification (on ne devine pas les comptes au chrono).
DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode()


def weak_password(password: str, *personal: str | None) -> str | None:
    """Motif du refus si le mot de passe est trop faible, sinon None."""
    low = password.lower()
    if low in COMMON or len(set(low)) <= 2:
        return (
            "Ce mot de passe est trop courant. Choisissez une phrase ou un mélange plus personnel."
        )
    for value in personal:
        for part in (value or "").lower().replace("@", " ").replace(".", " ").split():
            if len(part) >= 4 and part in low:
                return "Le mot de passe ne doit pas reprendre votre nom ou votre identifiant."
    return None


def create_session_tokens(
    user_id: UUID, token_version: int, session_id: UUID, rotation: int
) -> tuple[str, str]:
    """Jetons d'une session d'appareil : l'accès (30 min) et le rafraîchissement, qui porte
    la session et son numéro de rotation pour détecter un jeton réutilisé."""
    s = get_settings()
    now = datetime.now(UTC)
    base = {
        "sub": str(user_id),
        "ver": token_version,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
    }
    access = {
        **base,
        "typ": "access",
        "exp": int((now + timedelta(minutes=s.access_token_minutes)).timestamp()),
    }
    refresh = {
        **base,
        "typ": "refresh",
        "rot": rotation,
        "exp": int((now + timedelta(days=s.refresh_token_days)).timestamp()),
    }
    return (
        jwt.encode(access, s.jwt_secret, algorithm=s.jwt_algorithm),
        jwt.encode(refresh, s.jwt_secret, algorithm=s.jwt_algorithm),
    )
