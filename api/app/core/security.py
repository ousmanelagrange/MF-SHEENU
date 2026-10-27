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
