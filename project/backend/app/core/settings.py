from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
REPO_ROOT = PROJECT_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"
IMAGE_DIR = BACKEND_DIR / "insta_vibes"
FRONTEND_DIST_DIR = PROJECT_DIR / "frontend" / "dist"


def load_backend_env() -> None:
    load_dotenv(ENV_FILE)
