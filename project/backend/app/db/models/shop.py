from typing import TYPE_CHECKING

from sqlalchemy import Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.backend.app.db.base import Base

if TYPE_CHECKING:
    from project.backend.app.db.models.product import Product


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    url: Mapped[str | None] = mapped_column(Text)
    products: Mapped[list["Product"]] = relationship(back_populates="shop")
