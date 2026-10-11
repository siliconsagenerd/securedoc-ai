from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "securedoc-ai"
    database_url: str = "sqlite+aiosqlite:///./securedoc.db"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
