from fastapi import APIRouter

from project.backend.app.api.routes import auth, content, events, profile


api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(content.router, tags=["content"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(events.router, tags=["events"])
