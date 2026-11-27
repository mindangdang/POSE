from fastapi import APIRouter

from project.backend.app.api.routes import content
from project.backend.app.api.routes import auth
from project.backend.app.search.routes import router as search_v2_router
from project.backend.app.search.websocket import websocket_router


api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(content.router, tags=["content"])
api_router.include_router(search_v2_router, prefix="/v2", tags=["search-v2"])
api_router.include_router(websocket_router, prefix="/v2", tags=["search-v2"])
