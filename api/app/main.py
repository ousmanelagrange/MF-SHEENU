from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.routers import audit, auth, families, invitations, persons, relations, titles, tree

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de Sheenu — mémoire et organisation des grandes familles africaines.",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

api = APIRouter(prefix="/api/v1")
for module in (auth, families, invitations, persons, relations, tree, titles, audit):
    api.include_router(module.router)
app.include_router(api)

if settings.storage_backend == "local":
    media = Path(settings.media_dir)
    media.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media), name="media")


@app.get("/health", tags=["system"])
def health() -> dict:
    """État du service. `rls_enforced` doit valoir true : un rôle superutilisateur ou
    BYPASSRLS ignorerait l'isolation des familles (voir docs/04-deploiement.md)."""
    with engine.connect() as conn:
        bypass = conn.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    return {"status": "ok", "version": app.version, "rls_enforced": not bypass}
