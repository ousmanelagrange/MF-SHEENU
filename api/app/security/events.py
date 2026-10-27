"""Journal des événements de sécurité.

Chaque événement est écrit dans sa propre transaction : il reste enregistré même si la
requête qui l'a provoqué échoue et annule ses changements (une connexion refusée, un accès
interdit). L'écriture ne doit jamais faire échouer la requête : une erreur ici est ignorée.
"""

import logging
from uuid import UUID

from fastapi import Request

from app.core.db import SessionLocal
from app.models import SecurityEvent

log = logging.getLogger("sheenu.security")

# Gravité de chaque type d'événement (« info » par défaut)
SEVERITY = {
    "login_failed": "info",
    "login_locked": "warning",
    "rate_limited": "warning",
    "foreign_family": "warning",
    "refresh_reuse": "critical",
    "bad_signature": "critical",
    "media_bad_signature": "warning",
    "upload_rejected": "warning",
    "server_error": "critical",
    "account_disabled": "warning",
    "password_changed": "info",  # nosec B105 : un niveau de gravité, pas un mot de passe
    "operator_action": "info",
}


def client_ip(request: Request | None) -> str | None:
    """Adresse du client. Derrière l'hébergeur, uvicorn est lancé avec --proxy-headers :
    request.client contient alors l'adresse réelle, pas celle du proxy."""
    return request.client.host if request and request.client else None


def record(
    kind: str,
    request: Request | None = None,
    user_id: UUID | None = None,
    **detail: object,
) -> None:
    severity = SEVERITY.get(kind, "info")
    ip = client_ip(request)
    path = request.url.path[:300] if request else None
    log.log(
        logging.WARNING if severity != "info" else logging.INFO,
        "%s ip=%s user=%s %s",
        kind,
        ip,
        user_id,
        detail,
    )
    try:
        with SessionLocal() as db:
            db.add(
                SecurityEvent(
                    kind=kind,
                    severity=severity,
                    user_id=user_id,
                    ip=ip,
                    path=path,
                    detail={k: str(v)[:200] for k, v in detail.items()},
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001  (le journal ne doit jamais casser la requête)
        log.exception("Échec d'écriture d'un événement de sécurité")
