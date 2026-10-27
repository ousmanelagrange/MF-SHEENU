"""Intergiciels ASGI de sécurité et de supervision, du plus extérieur au plus intérieur :

1. SecurityHeaders : en-têtes de protection sur toutes les réponses, et pas de cache
   intermédiaire pour les données de l'API ;
2. Metrics : identifiant de requête, compteurs par minute pour la supervision, limite de
   débit globale par adresse IP ;
3. BodyLimit : refuse les corps de requête trop lourds avant de les lire en entier ;
4. MediaSigning : signe les adresses de médias dans les réponses JSON (security/media.py) ;
5. Idempotency : une écriture rejouée avec la même clé n'est appliquée qu'une fois.

Écrits en ASGI pur (sans BaseHTTPMiddleware) pour rester légers et ne pas bloquer le streaming
des fichiers audio.
"""

import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import decode_token
from app.models import IdempotencyKey, RequestMetric
from app.security import media, ratelimit

API = "/api/v1"


async def _send_json(send, status: int, detail: dict, extra: list | None = None) -> None:  # noqa: ANN001
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    await send(
        {"type": "http.response.start", "status": status, "headers": headers + (extra or [])}
    )
    await send({"type": "http.response.body", "body": body})


def _header(scope, name: bytes) -> str | None:  # noqa: ANN001
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


# ---------- 1. En-têtes de sécurité ----------


class SecurityHeaders:
    def __init__(self, app):  # noqa: ANN001
        self.app = app
        self.production = get_settings().environment == "production"

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]

        async def wrapped(message):  # noqa: ANN001
            if message["type"] == "http.response.start":
                h = [(k, v) for k, v in message.get("headers", [])]
                h += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ]
                if path.startswith("/media/"):
                    # Les images s'affichent sur le site web, qui est sur un autre domaine
                    h.append((b"cross-origin-resource-policy", b"cross-origin"))
                elif not path.startswith(("/docs", "/redoc", "/openapi")):
                    h.append(
                        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
                    )
                    h.append((b"cross-origin-resource-policy", b"same-site"))
                if path.startswith(API):
                    h.append((b"cache-control", b"no-store"))
                if self.production:
                    h.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = h
            await send(message)

        await self.app(scope, receive, wrapped)


# ---------- 2. Mesures et limite globale ----------


class _Counters:
    """Compteurs de la minute en cours, versés en base au changement de minute."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.minute: datetime | None = None
        self.data = {"requests": 0, "errors_4xx": 0, "errors_5xx": 0, "total_ms": 0, "max_ms": 0}

    def add(self, status: int, ms: int) -> None:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        flush = None
        with self.lock:
            if self.minute and self.minute != now:
                flush = (self.minute, dict(self.data))
                self.data = dict.fromkeys(self.data, 0)
            self.minute = now
            d = self.data
            d["requests"] += 1
            d["errors_4xx"] += 400 <= status < 500
            d["errors_5xx"] += status >= 500
            d["total_ms"] += ms
            d["max_ms"] = max(d["max_ms"], ms)
        if flush:
            self.write(*flush)

    def flush(self) -> None:
        with self.lock:
            pending = (
                (self.minute, dict(self.data)) if self.minute and self.data["requests"] else None
            )
            self.data = dict.fromkeys(self.data, 0)
        if pending:
            self.write(*pending)

    @staticmethod
    def write(minute: datetime, d: dict) -> None:
        try:
            with SessionLocal() as db:
                stmt = insert(RequestMetric).values(minute=minute, **d)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["minute"],
                    set_={
                        "requests": RequestMetric.requests + stmt.excluded.requests,
                        "errors_4xx": RequestMetric.errors_4xx + stmt.excluded.errors_4xx,
                        "errors_5xx": RequestMetric.errors_5xx + stmt.excluded.errors_5xx,
                        "total_ms": RequestMetric.total_ms + stmt.excluded.total_ms,
                        "max_ms": stmt.excluded.max_ms,
                    },
                )
                db.execute(stmt)
                db.commit()
        except Exception:  # noqa: BLE001  (la supervision ne doit jamais casser une requête)
            logging.getLogger("sheenu.metrics").warning("Compteurs non enregistrés", exc_info=True)


counters = _Counters()


class Metrics:
    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = _header(scope, b"x-request-id") or uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = request_id
        ip = scope["client"][0] if scope.get("client") else "?"
        if scope["path"].startswith(API) and ratelimit.hit("global", ip) is not None:
            from app.security import events  # import tardif : évite un cycle

            events.record("rate_limited", None, bucket="global", key=ip)
            return await _send_json(
                send,
                429,
                {"code": "rate_limited", "message": "Trop de requêtes. Patientez un instant."},
            )
        start = time.perf_counter()
        status = {"code": 500}

        async def wrapped(message):  # noqa: ANN001
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, wrapped)
        finally:
            if scope["path"].startswith(API):
                counters.add(status["code"], int((time.perf_counter() - start) * 1000))


# ---------- 3. Taille des corps de requête ----------

MAX_UPLOAD = 32 * 1024 * 1024  # fichiers (le module de stockage applique ensuite sa propre limite)
MAX_JSON = 1024 * 1024  # 1 Mo : largement assez pour un long récit


class BodyTooLargeError(Exception):
    pass


class BodyLimit:
    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        ctype = _header(scope, b"content-type") or ""
        limit = MAX_UPLOAD if ctype.startswith("multipart/") else MAX_JSON
        declared = _header(scope, b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            return await _send_json(
                send, 413, {"code": "too_large", "message": "Contenu trop lourd."}
            )
        received = {"n": 0}

        async def counted():  # noqa: ANN202
            message = await receive()
            if message["type"] == "http.request":
                received["n"] += len(message.get("body", b""))
                if received["n"] > limit:  # corps sans longueur annoncée qui dépasse
                    raise BodyTooLargeError
            return message

        try:
            await self.app(scope, counted, send)
        except BodyTooLargeError:
            await _send_json(send, 413, {"code": "too_large", "message": "Contenu trop lourd."})


# ---------- 4. Signature des médias ----------


class MediaSigning:
    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http" or not scope["path"].startswith(API):
            return await self.app(scope, receive, send)
        start: dict = {}
        chunks: list[bytes] = []

        async def wrapped(message):  # noqa: ANN001
            if message["type"] == "http.response.start":
                ctype = dict(message.get("headers", [])).get(b"content-type", b"")
                if not ctype.startswith(b"application/json"):
                    start["pass"] = True
                    return await send(message)
                start["message"] = message
                return None
            if start.get("pass"):
                return await send(message)
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return None
            body = media.sign_text(b"".join(chunks).decode()).encode()
            first = start["message"]
            first["headers"] = [(k, v) for k, v in first["headers"] if k != b"content-length"]
            first["headers"].append((b"content-length", str(len(body)).encode()))
            await send(first)
            await send({"type": "http.response.body", "body": body})
            return None

        await self.app(scope, receive, wrapped)


# ---------- 5. Idempotence des écritures ----------


class Idempotency:
    """Une requête d'écriture qui porte « Idempotency-Key » est mémorisée 48 heures avec sa
    réponse. Rejouée (même compte, même clé, même contenu), elle renvoie la même réponse sans
    rien refaire. Rejouée avec un autre contenu : refusée. Encore en cours : « réessayez »."""

    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        key = _header(scope, b"idempotency-key") if scope["type"] == "http" else None
        if (
            not key
            or scope["method"] not in ("POST", "PUT", "PATCH", "DELETE")
            or not scope["path"].startswith(API)
        ):
            return await self.app(scope, receive, send)
        user_id = self._user(scope)
        if user_id is None or len(key) > 100:
            return await self.app(scope, receive, send)

        # Lire le corps, pour l'empreinte, puis le rendre à l'application
        body = b""
        more = True
        while more:
            message = await receive()
            body += message.get("body", b"")
            more = message.get("more_body", False)
        digest = hashlib.sha256(
            scope["method"].encode() + scope["path"].encode() + body
        ).hexdigest()

        async def replay():  # noqa: ANN202
            return {"type": "http.request", "body": body, "more_body": False}

        with SessionLocal() as db:
            row = db.get(IdempotencyKey, (user_id, key))
            if row is None:
                db.add(IdempotencyKey(user_id=user_id, key=key, request_hash=digest))
                try:
                    db.commit()
                except IntegrityError:  # même clé arrivée au même instant
                    return await _send_json(
                        send, 409, {"code": "in_progress", "message": "Envoi déjà en cours."}
                    )
            elif row.request_hash != digest:
                return await _send_json(
                    send,
                    422,
                    {
                        "code": "idempotency_mismatch",
                        "message": "Clé déjà utilisée pour un autre envoi.",
                    },
                )
            elif row.status_code == 0:
                return await _send_json(
                    send, 409, {"code": "in_progress", "message": "Envoi déjà en cours."}
                )
            else:
                payload = (row.response_body or "").encode()
                headers = [
                    (b"content-type", b"application/json"),
                    (b"idempotent-replayed", b"true"),
                ]
                if payload:
                    headers.append((b"content-length", str(len(payload)).encode()))
                await send(
                    {"type": "http.response.start", "status": row.status_code, "headers": headers}
                )
                await send({"type": "http.response.body", "body": payload})
                return None

        status = {"code": 500}
        out: list[bytes] = []

        async def capture(message):  # noqa: ANN001
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            elif message["type"] == "http.response.body":
                out.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, replay, capture)
        finally:
            self._store(user_id, key, status["code"], b"".join(out))

    @staticmethod
    def _user(scope) -> uuid.UUID | None:  # noqa: ANN001
        auth = _header(scope, b"authorization") or ""
        if not auth.lower().startswith("bearer "):
            return None
        try:
            return uuid.UUID(decode_token(auth[7:])["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return None

    @staticmethod
    def _store(user_id: uuid.UUID, key: str, status: int, body: bytes) -> None:
        with SessionLocal() as db:
            row = db.get(IdempotencyKey, (user_id, key))
            if row is None:
                return
            if status >= 500:  # erreur serveur : on libère la clé pour pouvoir réessayer
                db.delete(row)
            else:
                row.status_code = status
                row.response_body = body.decode(errors="replace")
            db.commit()


def purge_idempotency(hours: int = 48) -> int:
    """Efface les clés plus anciennes que `hours` (appelé par la supervision)."""
    with SessionLocal() as db:
        cutoff = datetime.fromtimestamp(time.time() - hours * 3600, UTC)
        rows = list(db.scalars(select(IdempotencyKey).where(IdempotencyKey.created_at < cutoff)))
        for r in rows:
            db.delete(r)
        db.commit()
        return len(rows)
