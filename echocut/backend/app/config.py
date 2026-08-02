from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://echocut:echocut@localhost:5432/echocut"
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "echocut"
    clickhouse_username: str = "default"
    clickhouse_password: str = ""
    clickhouse_secure: bool = False
    clickhouse_mcp_command: str | None = None
    clickhouse_mcp_args: str = ""
    auth_mode: Literal["development", "firebase"] = "development"
    allow_development_auth: bool = False
    development_user_email: str = "editor@local.echocut"
    development_user_name: str = "Local Editor"
    firebase_project_id: str | None = None
    google_cloud_project: str | None = None
    google_cloud_region: str = "africa-south1"
    gcs_bucket: str | None = None
    local_storage_path: str = "./data/uploads"
    cors_allowed_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    request_timeout_seconds: float = Field(default=10, gt=0, le=60)
    extraction_mode: Literal["local", "gemini"] = "local"
    gemini_model: str = "gemini-2.5-flash"

    @model_validator(mode="after")
    def production_auth_guard(self) -> "Settings":
        if (
            self.app_env == "production"
            and self.auth_mode == "development"
            and not self.allow_development_auth
        ):
            raise ValueError("Development authentication is blocked in production")
        if self.auth_mode == "firebase" and not self.firebase_project_id:
            raise ValueError("FIREBASE_PROJECT_ID is required for Firebase authentication")
        if self.extraction_mode == "gemini" and not self.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Gemini extraction")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_allowed_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
