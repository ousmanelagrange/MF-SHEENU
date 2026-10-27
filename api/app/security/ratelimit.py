"""Limitation de débit par fenêtre glissante, en mémoire du processus.

Suffisant pour une instance unique (offre gratuite) ; avec plusieurs instances, chaque
processus compte de son côté, la limite réelle est multipliée d'autant. Le verrouillage
des comptes, lui, est stocké en base (voir modules/auth) et vaut pour toutes les instances.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError
from app.security import events

# Règles : (nombre de requêtes, fenêtre en secondes) par catégorie
RULES = {
    "login": (10, 60),  # par adresse IP : 10 essais par minute
    "register": (5, 3600),  # 5 comptes par heure et par IP
    "refresh": (60, 60),
    "join": (20, 3600),  # demandes de rattachement
    "upload": (60, 3600),  # 60 fichiers par heure et par compte
    "password": (5, 3600),
    "webhook": (120, 60),
    "global": (600, 60),  # tout le trafic d'une IP : 10 requêtes par seconde en moyenne
}

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def hit(bucket: str, key: str) -> float | None:
    """Compte une requête ; renvoie None si elle passe, sinon le délai d'attente en secondes."""
    if not get_settings().rate_limit:
        return None
    limit, window = RULES[bucket]
    now = time.monotonic()
    with _lock:
        q = _hits[(bucket, key)]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return window - (now - q[0])
        q.append(now)
    return None


def enforce(bucket: str, key: str, request: Request | None = None) -> None:
    wait = hit(bucket, key)
    if wait is not None:
        events.record("rate_limited", request, bucket=bucket, key=key)
        raise AppError(
            429, "rate_limited", f"Trop de tentatives. Réessayez dans {int(wait) + 1} s."
        )


def limit(bucket: str):  # noqa: ANN201
    """Dépendance FastAPI : limite la route par adresse IP."""

    def dependency(request: Request) -> None:
        enforce(bucket, events.client_ip(request) or "?", request)

    return dependency


def reset() -> None:
    """Remise à zéro (tests)."""
    with _lock:
        _hits.clear()
