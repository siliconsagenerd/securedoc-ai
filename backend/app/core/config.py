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
    gemini_model: str = "gemini-3.8-flash"
    # OpenAI-compatible provider (e.g. OmniRoute). Empty => use Gemini directly.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_fallback_models: str = ""
    app_env: str = "development"
    database_url: str = "sqlite:///./data/securedoc.db"
    audit_log_path: str = "./data/audit.log"
    token_vault_key: str = ""
    securedoc_api_key: str = ""
    injection_block_threshold: int = 40
    java_validator_url: str = "http://localhost:8080"
    # Comma-separated list of browser origins allowed to call the API. In
    # production set this to the Vercel dashboard origin (and nothing else).
    allowed_cors_origins: str = "http://localhost:5173"
    max_upload_size_mb: int = 5
    max_text_chars: int = 20_000
    rate_limit_per_minute: int = 20

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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
