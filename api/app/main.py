"""Point d'entrée de l'API : assemble les modules, configure CORS et la compression."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.contributions.router import router as contributions_router
from app.modules.data.router import router as data_router
from app.modules.delegations.router import router as delegations_router
from app.modules.families.router import router as families_router
from app.modules.family_merges.router import router as family_merges_router
from app.modules.invitations.router import router as invitations_router
from app.modules.memory.router import router as memory_router
from app.modules.persons.router import router as persons_router
from app.modules.proposals.router import router as proposals_router
from app.modules.relations.router import router as relations_router
from app.modules.social.router import router as social_router
from app.modules.titles.router import router as titles_router
from app.modules.tree.router import router as tree_router
from app.modules.uploads.router import router as uploads_router

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
):
    api.include_router(module_router)
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
