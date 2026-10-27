"""Stockage des photos : disque local en développement, S3 / Cloudflare R2 en production."""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.core.errors import bad_request

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 800


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


def save_photo(family_id: uuid.UUID, raw: bytes) -> str:
    """Enregistre l'image redimensionnée et renvoie son URL publique."""
    data = process_image(raw)
    s = get_settings()
    key = f"families/{family_id}/photos/{uuid.uuid4().hex}.webp"
    if s.storage_backend == "s3":
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name="auto",
        )
        client.put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType="image/webp")
        return f"{s.s3_public_url.rstrip('/')}/{key}"
    path = Path(s.media_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"{s.public_api_url.rstrip('/')}/media/{key}"
