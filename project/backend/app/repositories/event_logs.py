from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from project.backend.app.db.models.event_log import EventLog
from project.backend.app.schemas.requests import EventLogCreate


@dataclass(slots=True)
class EventLogsRepository:
    session: AsyncSession

    async def create(self, *, user_id: int, event: EventLogCreate) -> EventLog:
        event_log = EventLog(
            user_id=user_id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            metadata_=event.metadata or {},
            occurred_at=event.timestamp or datetime.now(timezone.utc),
        )
        self.session.add(event_log)
        await self.session.flush()
        return event_log
