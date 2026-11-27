from __future__ import annotations

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from project.backend.app.manage.settings import get_settings
from project.backend.app.runtime.sessions import TERMINAL_STATUSES


websocket_router = APIRouter()

@websocket_router.websocket("/ws/{search_id}")
async def search_events(websocket: WebSocket, search_id: str) -> None:
    settings = get_settings()
    token = websocket.query_params.get("token", "")
    if not settings.jwt_secret:
        await websocket.close(code=4401)
        return
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        owner_id = str(claims["sub"])
    except Exception:
        await websocket.close(code=4401)
        return
    registry = getattr(websocket.app.state, "pose_search_registry", None)
    session = registry.sessions.get(search_id) if registry else None
    if not session or session.owner_id != owner_id:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    last_sequence = 0
    try:
        while True:
            async with session.condition:
                await session.condition.wait_for(
                    lambda: any(event["sequence"] > last_sequence for event in session.events)
                    or session.status in TERMINAL_STATUSES
                )
                new_events = [event for event in session.events if event["sequence"] > last_sequence]
            for event in new_events:
                await websocket.send_json(event)
                last_sequence = event["sequence"]
            if session.status in TERMINAL_STATUSES:
                return
    except WebSocketDisconnect:
        return
