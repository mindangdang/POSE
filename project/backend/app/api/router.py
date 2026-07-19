from fastapi import APIRouter

from project.backend.app.api.routes import content
from project.backend.app.api.routes import auth


api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(content.router, tags=["content"])
