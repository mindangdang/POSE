from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.backend.app.db.base import Base

if TYPE_CHECKING:
    from project.backend.app.db.models.product import Product
    from project.backend.app.db.models.user import User


class SavedPost(Base):
    __tablename__ = "saved_posts"

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "product_db.id",
            name="fk_saved_posts_product_id_product_db",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_saved_posts_user_id_users",
            ondelete="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )
    user: Mapped["User"] = relationship(back_populates="saved_posts")
    product: Mapped["Product"] = relationship(back_populates="saved_posts")
