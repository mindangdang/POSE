from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Identity, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.backend.app.db.base import Base

if TYPE_CHECKING:
    from project.backend.app.db.models.event_log import EventLog
    from project.backend.app.db.models.saved_post import SavedPost


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    oauth_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    profile_image: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )
    saved_posts: Mapped[list["SavedPost"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    event_logs: Mapped[list["EventLog"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
