from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from project.backend.app.api.router import api_router
from project.backend.app.core.database import lifespan
from project.backend.app.api.routes.web import router as web_router
from project.backend.app.core.settings import FRONTEND_DIST_DIR, IMAGE_DIR, load_backend_env


def create_app() -> FastAPI:
    load_backend_env()

    app = FastAPI(lifespan=lifespan)

    IMAGE_DIR.mkdir(exist_ok=True)
    app.mount("/api/images", StaticFiles(directory=str(IMAGE_DIR)), name="images")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    app.include_router(api_router, prefix="/api")
    app.include_router(web_router)
    return app
