from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_user: str = "mynews"
    postgres_password: str = "mynews"
    postgres_db: str = "mynews"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # App
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    scheduler_enabled: bool = True
    cookie_secure: bool = False

    # Gemini (free tier)
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model_lite: str = "gemini-3.5-flash-lite"
    gemini_model_flash: str = "gemini-3.8-flash"
    gemini_model_embedding: str = "gemini-embedding-2"
    embedding_dimensions: int = 768
    # Own per-model limits; 0 = unlimited (only the backoff on Google's 429 applies).
    gemini_rpm: int = 0
    gemini_rpd: int = 0

    # Ingestion
    http_timeout_seconds: float = 20.0
    http_concurrency: int = 8

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
