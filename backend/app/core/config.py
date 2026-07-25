from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


LOCAL_FRONTEND_URL = "http://localhost:5173"
PRODUCTION_FRONTEND_URL = "https://kondai-flax.vercel.app"
LOCAL_API_URL = "http://localhost:8000"
PRODUCTION_API_URL = "https://kondai.onrender.com"


class Settings(BaseSettings):
    app_name: str = "Kondai API"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"

    # OAuth callbacks redirect users to this frontend after completing a flow.
    # Render should override this with https://kondai-flax.vercel.app.
    frontend_url: str = LOCAL_FRONTEND_URL

    # Comma-separated browser origins accepted by FastAPI CORS.
    # Both local development and the production Vercel app are included by
    # default so a missing Render variable cannot silently break production.
    cors_origins: str = (
        f"{LOCAL_FRONTEND_URL},"
        "http://127.0.0.1:5173,"
        f"{PRODUCTION_FRONTEND_URL}"
    )

    auth_mode: str = "dev"
    dev_user_id: str = "local-founder"
    dev_workspace_id: str = "local-workspace"

    store_mode: str = "json"
    json_store_path: str = "data/store.json"
    firebase_project_id: str = ""
    firebase_service_account_path: str = ""

    ai_mode: str = "deterministic"
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"

    outbound_mode: str = "mock"
    support_confidence_threshold: float = 0.72
    max_daily_executions: int = 50

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = ""
    github_oauth_scope: str = "repo read:user"
    github_api_version: str = "2022-11-28"
    github_sync_file_limit: int = 1000
    github_sync_manifest_limit: int = 24
    github_sync_file_size_limit: int = 100000

    integration_encryption_key: str = ""
    firestore_sync_document_limit: int = 2500
    stripe_sync_page_limit: int = 5
    posthog_default_host: str = "https://us.posthog.com"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    gmail_redirect_uri: str = ""
    gmail_oauth_scope: str = (
        "openid email https://www.googleapis.com/auth/gmail.readonly"
    )
    gmail_default_query: str = (
        "in:inbox newer_than:30d -category:promotions -category:social"
    )
    gmail_sync_limit: int = 100

    whatsapp_graph_version: str = "v25.0"
    whatsapp_customer_window_hours: int = 24
    whatsapp_message_body_limit: int = 4096

    # Platform-level Meta configuration. Founders never enter these values.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_embedded_signup_config_id: str = ""
    meta_embedded_signup_redirect_uri: str = ""
    meta_embedded_signup_feature_type: str = ""
    meta_webhook_verify_token: str = ""

    # Local by default; Render should override this with
    # https://kondai.onrender.com.
    public_api_base_url: str = LOCAL_API_URL
    meta_auto_register_phone_number: bool = True

    model_config = SettingsConfigDict(
        # Local development can use backend/.env or backend/.env.local.
        # Real Render environment variables override both files.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("frontend_url", "public_api_base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @field_validator("api_prefix", mode="before")
    @classmethod
    def normalize_api_prefix(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().strip("/")
        return f"/{cleaned}" if cleaned else "/api/v1"

    @model_validator(mode="after")
    def derive_oauth_callbacks(self) -> "Settings":
        base = self.public_api_base_url.rstrip("/")
        prefix = self.api_prefix.rstrip("/")

        if not self.github_redirect_uri.strip():
            self.github_redirect_uri = (
                f"{base}{prefix}/integrations/github/oauth/callback"
            )

        if not self.gmail_redirect_uri.strip():
            self.gmail_redirect_uri = (
                f"{base}{prefix}/integrations/gmail/oauth/callback"
            )

        return self

    @property
    def allowed_origins(self) -> list[str]:
        """Return exact, normalized and de-duplicated CORS origins."""
        candidates = [
            LOCAL_FRONTEND_URL,
            "http://127.0.0.1:5173",
            PRODUCTION_FRONTEND_URL,
            self.frontend_url,
            *self.cors_origins.split(","),
        ]

        origins: list[str] = []
        for candidate in candidates:
            origin = candidate.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
