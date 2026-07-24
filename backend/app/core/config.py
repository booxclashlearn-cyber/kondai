from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Kondai API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"

    auth_mode: str = "dev"
    dev_user_id: str = "local-founder"
    dev_workspace_id: str = "local-workspace"

    store_mode: str = "json"
    json_store_path: str = "data/store.json"
    firebase_project_id: str = ""
    firebase_service_account_path: str = ""

    ai_mode: str = "deterministic"
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-2.5-flash"

    outbound_mode: str = "mock"
    support_confidence_threshold: float = 0.72
    max_daily_executions: int = 50

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = (
        "http://localhost:8000/api/v1/integrations/github/oauth/callback"
    )
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
    gmail_redirect_uri: str = (
        "http://localhost:8000/api/v1/integrations/gmail/oauth/callback"
    )
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
    public_api_base_url: str = "http://localhost:8000"
    meta_auto_register_phone_number: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
