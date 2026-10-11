"""Application configuration loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    app_env: str = "development"
    database_url: str = "sqlite:///./data/securedoc.db"
    audit_log_path: str = "./data/audit.log"
    token_vault_key: str = ""
    max_upload_size_mb: int = 5

    @model_validator(mode="after")
    def _ensure_directories(self) -> "Settings":
        """Create parent directories for the DB and audit log automatically."""
        for path in (self.db_path, self.audit_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def db_path(self) -> Path:
        return Path(self.database_url.removeprefix("sqlite:///"))

    @property
    def audit_path(self) -> Path:
        return Path(self.audit_log_path)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
