"""Aides HTTP partagées."""

import unicodedata
from urllib.parse import quote


def attachment(filename: str) -> str:
    """En-tête Content-Disposition pour un téléchargement, accents compris.

    Les en-têtes HTTP n'acceptent que l'ASCII : on donne un nom sans accents pour les vieux
    navigateurs (filename) et le nom exact encodé pour les autres (filename*, RFC 6266).
    """
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = (
        "".join(ch for ch in ascii_name if ch.isalnum() or ch in " -_.").strip() or "export"
    )
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
