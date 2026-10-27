"""Éléments communs aux modèles : horodatage UTC et identifiants."""

import uuid
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Horodatage en UTC (toutes les dates sont stockées en UTC)."""
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    """Identifiant généré par l'application."""
    return uuid.uuid4()
