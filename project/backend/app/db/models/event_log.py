from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.backend.app.db.base import Base

if TYPE_CHECKING:
    from project.backend.app.db.models.user import User


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("idx_event_logs_user_action", "user_id", "action"),
        Index("idx_event_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_event_logs_user_id_users",
            ondelete="SET NULL",
        ),
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    user: Mapped["User | None"] = relationship(back_populates="event_logs")
