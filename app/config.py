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

    # JWT Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_callback_base_url: str = ""  # e.g. https://essertaize.com

    # Apple App Store
    apple_bundle_id: str = ""
    apple_issuer_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

    # Google Play Store
    google_play_package_name: str = ""
    google_service_account_json: str = ""

    # Rate Limiting
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_ai: str = "10/minute"

    # Subscription product IDs
    subscription_student_apple_id: str = "com.knowit.student"
    subscription_unlimited_apple_id: str = "com.knowit.unlimited"
    subscription_student_google_id: str = "com.knowit.student"
    subscription_unlimited_google_id: str = "com.knowit.unlimited"

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