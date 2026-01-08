"""
Configuration management using pydantic-settings.
Loads environment variables with type validation.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "KnowIt Backend"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4"
    whisper_model: str = "whisper-1"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8081"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    Use dependency injection in FastAPI routes.
    """
    return Settings()
