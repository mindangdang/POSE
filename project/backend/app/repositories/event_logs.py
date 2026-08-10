from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from project.backend.app.schemas.requests import EventLogCreate


@dataclass(slots=True)
class EventLogsRepository:
    conn: Any

    async def create(self, *, user_id: int, event: EventLogCreate) -> int | None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO event_logs (user_id, action, entity_type, entity_id, metadata, occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    event.action,
                    event.entity_type,
                    event.entity_id,
                    Jsonb(event.metadata or {}),
                    event.timestamp or datetime.now(timezone.utc),
                ),
            )
            row = await cursor.fetchone()
            await self.conn.commit()
            return int(row[0]) if row else None
