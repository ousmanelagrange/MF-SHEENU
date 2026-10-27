"""Médias privés : adresses signées et à durée limitée.

Les photos et enregistrements d'une famille ne sont jamais accessibles par une adresse fixe.
Les adresses enregistrées en base sont « canoniques » (sans signature) ; à chaque réponse
de l'API, elles sont remplacées par une adresse signée valable quelques heures :

- stockage local : /media/<clé>?exp=<expiration>&sig=<HMAC>, vérifié par la route /media ;
- Cloudflare R2 / S3 : URL présignée du fournisseur (le bucket doit rester privé).

Une adresse copiée hors de l'application cesse donc de fonctionner à son expiration.
"""

import base64
import hashlib
import hmac
import re
import time
from functools import lru_cache

from app.core.config import get_settings
from app.core.errors import bad_request

TTL = 6 * 3600  # durée de validité d'une adresse signée
KEY = r"(families/[0-9a-f-]{36}/(?:photos|media)/[0-9a-f]{32}\.[a-z0-9]{2,5})"
SIGNATURE = r"(?:\?exp=\d+(?:&|&amp;)sig=[A-Za-z0-9_-]+)?"


def _secret() -> bytes:
    return hashlib.sha256(b"sheenu-media:" + get_settings().jwt_secret.encode()).digest()


def _sig(key: str, exp: int) -> str:
    mac = hmac.new(_secret(), f"{key}:{exp}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac[:18]).decode().rstrip("=")


def verify(key: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(_sig(key, exp), sig)


def _expiry() -> int:
    # Arrondie à l'heure : la même adresse pendant une heure, que le navigateur peut garder en cache
    now = int(time.time())
    return (now // 3600) * 3600 + TTL


@lru_cache
def _patterns() -> list[tuple[re.Pattern, str]]:
    s = get_settings()
    out = [
        (re.compile(re.escape(s.public_api_url.rstrip("/") + "/media/") + KEY + SIGNATURE), "local")
    ]
    if s.s3_public_url:
        out.append(
            (re.compile(re.escape(s.s3_public_url.rstrip("/") + "/") + KEY + SIGNATURE), "s3")
        )
    return out


@lru_cache
def _s3_client():  # noqa: ANN202
    import boto3

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name="auto",
    )


def signed(key: str, backend: str) -> str:
    s = get_settings()
    if backend == "s3":
        return _s3_client().generate_presigned_url(
            "get_object", Params={"Bucket": s.s3_bucket, "Key": key}, ExpiresIn=TTL
        )
    exp = _expiry()
    return f"{s.public_api_url.rstrip('/')}/media/{key}?exp={exp}&sig={_sig(key, exp)}"


def sign_text(text: str) -> str:
    """Remplace chaque adresse de média d'un texte (une réponse JSON) par sa version signée."""
    for pattern, backend in _patterns():
        text = pattern.sub(lambda m, b=backend: signed(m.group(1), b), text)
    return text


def canonical(url: str) -> tuple[str, str] | None:
    """(adresse sans signature, clé) si l'adresse désigne un média de Sheenu, sinon None."""
    for pattern, _ in _patterns():
        m = pattern.fullmatch(url.strip())
        if m:
            return url.strip().split("?", 1)[0], m.group(1)
    return None


def own_media(family_id, url: str) -> str:  # noqa: ANN001
    """Vérifie qu'une adresse envoyée par un client désigne un média de SA famille et renvoie
    sa forme canonique. Refuse les liens externes (pixels de suivi, contenus non contrôlés)
    et les médias d'une autre famille."""
    found = canonical(url)
    if not found or not found[1].startswith(f"families/{family_id}/"):
        raise bad_request("invalid_media", "Ce média doit être envoyé depuis Sheenu.")
    return found[0]
