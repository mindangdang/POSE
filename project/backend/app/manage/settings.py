from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
REPO_ROOT = PROJECT_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"
IMAGE_DIR = BACKEND_DIR / "insta_vibes"
FRONTEND_DIST_DIR = PROJECT_DIR / "frontend" / "dist"


class Settings(BaseSettings):
    google_client_id: str | None = None
    jwt_secret: str | None = None
    neon_db_url: str | None = None
    google_api_key: str | None = None
    gpu_server_url: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None
    apify_api_key: str | None = None
    serp_api_key: str | None = None
    backend_port: int | None = None
    port: int | None = None
    residential_proxy_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
