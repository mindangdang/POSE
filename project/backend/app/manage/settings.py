from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    serp_api_key: str | None = None
    serpapi_api_key: str | None = None
    search_provider: str = "serpapi"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = Field(default=1, ge=0, le=3)
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    backend_port: int = 8000
    pose_fetch_evidence: bool = False
    model_server_timeout_seconds: float = 20.0
    search_max_rounds: int = 2
    search_max_queries_per_round: int = 3
    search_max_external_calls: int = 6
    search_max_concurrency: int = 4
    search_max_candidates: int = 50
    search_max_evidence_documents: int = 15
    search_max_reranker_candidates: int = Field(default=30, ge=0, le=30)
    search_deadline_seconds: float = 60.0
    search_result_threshold: float = 0.5
    search_relevance_weight: float = Field(default=0.40, ge=0, le=1)
    search_preference_weight: float = Field(default=0.20, ge=0, le=1)
    search_constraint_weight: float = Field(default=0.25, ge=0, le=1)
    search_evidence_weight: float = Field(default=0.15, ge=0, le=1)
    search_uncertainty_penalty: float = Field(default=0.15, ge=0, le=1)
    base_proxy_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
