from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Kondai API"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"

    # The frontend to redirect users back to after OAuth.
    # Override this in Render with https://kondai-flax.vercel.app
    frontend_url: str = "http://localhost:5173"

    # Comma-separated origins accepted by FastAPI CORS.
    # Keeping both allows local frontend development against either local or
    # deployed backend, while production can serve the Vercel frontend.
    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://kondai-flax.vercel.app"
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

    # Leave blank to derive automatically from PUBLIC_API_BASE_URL.
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

    # Leave blank to derive automatically from PUBLIC_API_BASE_URL.
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

    # Local default. Override in Render with https://kondai.onrender.com
    public_api_base_url: str = "http://localhost:8000"

    meta_auto_register_phone_number: bool = True

    model_config = SettingsConfigDict(
        # .env.local overrides .env locally. Render environment variables
        # override both files in production.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "frontend_url",
        "public_api_base_url",
        mode="before",
    )
    @classmethod
    def strip_trailing_slash(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @field_validator("api_prefix", mode="before")
    @classmethod
    def normalize_api_prefix(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            return "/api/v1"
        return "/" + cleaned.strip("/")

    @model_validator(mode="after")
    def build_oauth_redirect_uris(self) -> "Settings":
        base_url = self.public_api_base_url.rstrip("/")
        api_prefix = self.api_prefix.rstrip("/")

        if not self.github_redirect_uri.strip():
            self.github_redirect_uri = (
                f"{base_url}{api_prefix}"
                "/integrations/github/oauth/callback"
            )

        if not self.gmail_redirect_uri.strip():
            self.gmail_redirect_uri = (
                f"{base_url}{api_prefix}"
                "/integrations/gmail/oauth/callback"
            )

        return self

    @property
    def allowed_origins(self) -> list[str]:
        """Return a clean, de-duplicated CORS origin list."""
        values = [self.frontend_url]
        values.extend(self.cors_origins.split(","))

        origins: list[str] = []
        for value in values:
            origin = value.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)

        return origins

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
