from fastapi import APIRouter

from project.backend.app.api.routes import content
from project.backend.app.api.routes import auth
from project.backend.search_engine.api import router as search_v2_router


api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(content.router, tags=["content"])
api_router.include_router(search_v2_router, prefix="/v2", tags=["search-v2"])
