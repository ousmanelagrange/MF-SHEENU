"""Stockage des fichiers (photos, enregistrements des récits) : disque local en développement,
S3 / Cloudflare R2 en production."""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.core.errors import bad_request

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 800
MAX_MEDIA_BYTES = 30 * 1024 * 1024  # un récit de 30 min en audio compressé tient largement

# Formats acceptés pour les récits : type MIME -> (extension, nature)
MEDIA_TYPES = {
    "audio/mpeg": ("mp3", "audio"),
    "audio/mp4": ("m4a", "audio"),
    "audio/x-m4a": ("m4a", "audio"),
    "audio/aac": ("aac", "audio"),
    "audio/ogg": ("ogg", "audio"),
    "audio/webm": ("webm", "audio"),
    "audio/wav": ("wav", "audio"),
    "video/mp4": ("mp4", "video"),
    "video/webm": ("webm", "video"),
    "video/quicktime": ("mov", "video"),
}


def process_image(raw: bytes) -> bytes:
    if len(raw) > MAX_BYTES:
        raise bad_request("file_too_large", "Image trop lourde (5 Mo maximum).")
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise bad_request("invalid_image", "Fichier image illisible.") from exc
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=82)
    return out.getvalue()


def _put(key: str, data: bytes, content_type: str) -> str:
    """Range le fichier sous `key` et renvoie son adresse publique."""
    s = get_settings()
    if s.storage_backend == "s3":
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name="auto",
        )
        client.put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType=content_type)
        return f"{s.s3_public_url.rstrip('/')}/{key}"
    path = Path(s.media_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"{s.public_api_url.rstrip('/')}/media/{key}"


def save_photo(family_id: uuid.UUID, raw: bytes) -> str:
    """Enregistre l'image redimensionnée et renvoie son URL publique."""
    key = f"families/{family_id}/photos/{uuid.uuid4().hex}.webp"
    return _put(key, process_image(raw), "image/webp")


def save_media(family_id: uuid.UUID, raw: bytes, content_type: str | None) -> tuple[str, str]:
    """Enregistre un fichier audio ou vidéo tel quel ; renvoie (adresse, « audio » | « video »)."""
    base_type = (content_type or "").split(";")[0].strip().lower()
    if base_type not in MEDIA_TYPES:
        raise bad_request("invalid_media", "Format non pris en charge (audio ou vidéo attendu).")
    if len(raw) > MAX_MEDIA_BYTES:
        raise bad_request("file_too_large", "Fichier trop lourd (30 Mo maximum).")
    ext, kind = MEDIA_TYPES[base_type]
    key = f"families/{family_id}/media/{uuid.uuid4().hex}.{ext}"
    return _put(key, raw, base_type), kind
