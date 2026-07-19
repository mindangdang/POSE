from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb

from project.backend.app.api.dependencies import get_current_user
from project.backend.app.manage.database import get_db_connection
from project.backend.app.schemas.requests import EventBatchCreate

router = APIRouter()


@router.post("/events")
async def collect_events(
    payload: EventBatchCreate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
):
    authenticated_user_id = str(current_user.get("sub"))

    async with conn.cursor() as cur:
        for event in payload.events:
            await cur.execute(
                """
                INSERT INTO event_logs (
                    timestamp,
                    user_id,
                    session_id,
                    event_name,
                    properties,
                    page,
                    user_agent
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.timestamp,
                    authenticated_user_id,
                    event.session_id,
                    event.event_name,
                    Jsonb(event.properties),
                    event.page,
                    event.user_agent,
                ),
            )
        await conn.commit()

    return {"ok": True, "accepted": len(payload.events)}
