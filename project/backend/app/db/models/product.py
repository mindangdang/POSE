from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.backend.app.db.base import Base

if TYPE_CHECKING:
    from project.backend.app.db.models.saved_post import SavedPost
    from project.backend.app.db.models.shop import Shop


class Product(Base):
    __tablename__ = "product_db"
    __table_args__ = (UniqueConstraint("source_url", "title"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    title_vector: Mapped[list[float] | None] = mapped_column(Vector(768))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    brand: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    is_soldout: Mapped[bool | None] = mapped_column(Boolean)
    image_url: Mapped[str] = mapped_column(Text)
    image_vector: Mapped[list[float] | None] = mapped_column(Vector(768))
    shop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "shops.id",
            name="fk_product_db_shop_id_shops",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    gender: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        server_default=func.current_timestamp(),
    )
    saved_posts: Mapped[list["SavedPost"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    shop: Mapped["Shop"] = relationship(back_populates="products")
