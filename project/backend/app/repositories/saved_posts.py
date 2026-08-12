from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from project.backend.app.db.models.product import Product
from project.backend.app.db.models.saved_post import SavedPost
from project.backend.app.db.models.shop import Shop


@dataclass(slots=True)
class SavedPostsRepository:
    session: AsyncSession

    @staticmethod
    def _joined_columns():
        return (
            Product.id.label("product_id"),
            Product.source_url,
            Product.title,
            Product.price,
            Product.currency,
            Product.brand,
            Product.category,
            Product.is_soldout,
            Product.image_url,
            Product.image_vector,
            Shop.name.label("shop"),
            Product.gender,
            SavedPost.created_at,
        )

    async def create(self, *, user_id: int, product_id: int) -> None:
        statement = (
            insert(SavedPost)
            .values(user_id=user_id, product_id=product_id)
            .on_conflict_do_nothing(
                index_elements=[SavedPost.product_id, SavedPost.user_id]
            )
        )
        await self.session.execute(statement)

    async def insert_items_batch(
        self,
        *,
        user_id: int,
        product_ids: list[int],
    ) -> None:
        if not product_ids:
            return
        statement = (
            insert(SavedPost)
            .values(
                [
                    {"user_id": user_id, "product_id": product_id}
                    for product_id in product_ids
                ]
            )
            .on_conflict_do_nothing(
                index_elements=[SavedPost.product_id, SavedPost.user_id]
            )
        )
        await self.session.execute(statement)

    async def delete_by_id(self, product_id: int, user_id: int) -> None:
        await self.session.execute(
            delete(SavedPost).where(
                SavedPost.product_id == product_id,
                SavedPost.user_id == user_id,
            )
        )

    async def count_by_user_id(self, user_id: int) -> int:
        count = await self.session.scalar(
            select(func.count()).select_from(SavedPost).where(
                SavedPost.user_id == user_id
            )
        )
        return int(count or 0)

    def _joined_statement(self):
        return (
            select(*self._joined_columns())
            .join(Product, Product.id == SavedPost.product_id)
            .join(Shop, Shop.id == Product.shop_id)
        )

    async def list_feed_items(self, user_id: int) -> list[dict[str, Any]]:
        statement = (
            self._joined_statement()
            .where(SavedPost.user_id == user_id)
            .order_by(SavedPost.created_at.desc())
        )
        rows = (await self.session.execute(statement)).mappings().all()
        return jsonable_encoder([self._normalize_item(row) for row in rows])

    async def get_random_feed_item(self, user_id: int) -> dict[str, Any] | None:
        statement = (
            self._joined_statement()
            .where(SavedPost.user_id == user_id)
            .order_by(func.random())
            .limit(1)
        )
        row = (await self.session.execute(statement)).mappings().one_or_none()
        return jsonable_encoder(self._normalize_item(row)) if row else None

    @staticmethod
    def _normalize_item(item: Any) -> dict[str, Any]:
        normalized = dict(item)
        if normalized.get("image_vector") is not None:
            normalized["image_vector"] = str(normalized["image_vector"])
        return normalized
