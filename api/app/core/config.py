"""Configuration lue depuis les variables d'environnement (ou le fichier .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Sheenu API"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://lignee:lignee@localhost:5432/lignee"

    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30

    cors_origins: str = "http://localhost:5173,http://localhost:8081,http://localhost:19006"
    public_web_url: str = "http://localhost:5173"

    invitation_days: int = 7

    storage_backend: str = "local"  # local | s3
    media_dir: str = "media"
    public_api_url: str = "http://localhost:8000"
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_public_url: str | None = None

    # Messagerie (phase 6) : « share » prépare des liens WhatsApp à ouvrir soi-même (gratuit) ;
    # « whatsapp_cloud » envoie par l'API WhatsApp Business de Meta (payante, jetons requis).
    messaging_backend: str = "share"
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None

    # Paiement en ligne (phase 6) : « none » (déclaration manuelle seulement) ou « sandbox »
    # (simulation pour les tests). Un vrai prestataire Mobile Money s'ajoute dans
    # app/integrations/payments.py ; le secret signe les webhooks.
    payment_backend: str = "none"
    payment_webhook_secret: str = "change-me-webhook-secret"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        # Render/Neon fournissent souvent postgres:// ou postgresql:// : on force le pilote psycopg 3.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
