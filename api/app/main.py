"""Point d'entrée de l'API : assemble les modules, configure CORS et la compression."""

import logging
import re
import time
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.core.config import check_production, get_settings
from app.core.db import engine
from app.core.errors import AppError
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.contributions.online import router as contributions_online_router
from app.modules.contributions.router import router as contributions_router
from app.modules.data.router import router as data_router
from app.modules.delegations.router import router as delegations_router
from app.modules.families.router import router as families_router
from app.modules.family_merges.router import router as family_merges_router
from app.modules.invitations.router import router as invitations_router
from app.modules.join.router import router as join_router
from app.modules.memory.router import router as memory_router
from app.modules.notifications.router import router as notifications_router
from app.modules.overview.router import router as overview_router
from app.modules.persons.router import router as persons_router
from app.modules.platform.router import router as platform_router
from app.modules.proposals.router import router as proposals_router
from app.modules.relations.router import router as relations_router
from app.modules.social.router import router as social_router
from app.modules.titles.router import router as titles_router
from app.modules.tree.router import router as tree_router
from app.modules.uploads.router import router as uploads_router
from app.security import events
from app.security import media as media_security
from app.security.middleware import (
    BodyLimit,
    Idempotency,
    MediaSigning,
    Metrics,
    SecurityHeaders,
    counters,
)

settings = get_settings()
check_production(settings)  # refuse de démarrer avec une configuration de production faible

production = settings.environment == "production"
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de Sheenu — mémoire et organisation des grandes familles africaines.",
    # En production, pas de documentation publique de l'API (moins de surface exposée)
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

# Intergiciels : le dernier ajouté est le plus extérieur (voir security/middleware.py)
app.add_middleware(Idempotency)
app.add_middleware(MediaSigning)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(BodyLimit)
app.add_middleware(Metrics)
app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Family-Id",
        "Idempotency-Key",
        "X-Request-Id",
    ],
    expose_headers=["Content-Disposition"],
)

api = APIRouter(prefix="/api/v1")
for module_router in (
    auth_router,
    families_router,
    invitations_router,
    persons_router,
    relations_router,
    tree_router,
    titles_router,
    audit_router,
    proposals_router,
    delegations_router,
    data_router,
    contributions_router,
    family_merges_router,
    uploads_router,
    social_router,
    memory_router,
    contributions_online_router,
    notifications_router,
    join_router,
    overview_router,
    platform_router,
):
    api.include_router(module_router)
app.include_router(api)

MEDIA_ROOT = Path(settings.media_dir).resolve()
MEDIA_KEY = re.compile(media_security.KEY)


@app.get("/media/{key:path}", include_in_schema=False)
def media_file(key: str, request: Request, exp: int = 0, sig: str = "") -> FileResponse:
    """Médias du stockage local, seulement avec une adresse signée et non expirée."""
    if not MEDIA_KEY.fullmatch(key) or not media_security.verify(key, exp, sig):
        events.record("media_bad_signature", request, key=key[:80])
        raise AppError(403, "forbidden", "Lien expiré ou invalide.")
    path = (MEDIA_ROOT / key).resolve()
    if not path.is_relative_to(MEDIA_ROOT) or not path.is_file():
        raise AppError(404, "not_found", "Fichier introuvable.")
    remaining = max(0, exp - int(time.time()))
    return FileResponse(path, headers={"Cache-Control": f"private, max-age={remaining}"})


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception) -> JSONResponse:
    """Erreur imprévue : rien de technique n'est montré au client ; l'incident est journalisé
    avec son identifiant de requête pour la supervision."""
    request_id = request.scope.get("state", {}).get("request_id")
    logging.getLogger("sheenu").exception("Erreur serveur %s", request_id)
    events.record("server_error", request, error=type(exc).__name__, request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "server_error",
                "message": f"Erreur interne, incident {request_id} enregistré.",
            }
        },
    )


@app.on_event("shutdown")
def flush_metrics() -> None:
    counters.flush()


@app.get("/health", tags=["system"])
def health() -> dict:
    """État du service. `rls_enforced` doit valoir true : un rôle superutilisateur ou
    BYPASSRLS ignorerait l'isolation des familles (voir docs/04-deploiement.md)."""
    with engine.connect() as conn:
        bypass = conn.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    return {"status": "ok", "version": app.version, "rls_enforced": not bypass}
