"""
Application configuration.

All configuration is loaded from environment variables (see .env.example).
Nothing secret is hard-coded or committed to source control.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    APP_NAME: str = "Instagram Post Optimizer"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "dev-secret-key-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/instaopt"
    )

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- Instagram / Meta integration ---
    # Which provider implementation to use. "mock" requires no credentials
    # and is the default for local development / MVP demos.
    INSTAGRAM_PROVIDER: str = "mock"

    # Real Meta credentials (only required when INSTAGRAM_PROVIDER=meta).
    # These are the **Instagram** App ID/Secret found under the Meta app's
    # Instagram product ("API setup with Instagram login") -- NOT the
    # Facebook App ID/Secret on the main app settings page.
    # NEVER commit real values. Populate these via your deployment
    # environment's secret manager or a local, git-ignored .env file.
    META_APP_ID: str | None = None
    META_APP_SECRET: str | None = None
    # Must be HTTPS -- Instagram rejects plain http://localhost. Use a
    # tunnel (cloudflared/ngrok) for local development.
    META_REDIRECT_URI: str | None = None
    META_GRAPH_API_VERSION: str = "v23.0"

    # Where to send the browser after an OAuth callback completes.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Caption generation (optional) ---
    # Claude API key, used only by the caption-suggestion feature. When
    # unset, that endpoint returns a clear "not configured" error and the
    # rest of the app is unaffected. NEVER commit a real key.
    ANTHROPIC_API_KEY: str | None = None
    CAPTION_MODEL: str = "claude-opus-5"

    # --- File storage ---
    # Defaults are relative to the backend/ working directory for local,
    # non-Docker development. docker-compose.yml overrides these to
    # /app/storage/... (a mounted volume) for containerized runs.
    UPLOAD_DIR: str = "storage/uploads"
    VARIANT_DIR: str = "storage/variants"
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_IMAGE_CONTENT_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
