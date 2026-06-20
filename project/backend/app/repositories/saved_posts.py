from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row


@dataclass(slots=True)
class SavedPostsRepository:
    conn: Any

    _INSERT_COLUMNS = (
        "user_id, source_url, category, title, price, brand, is_available, image_url, image_vector, shop"
    )
    _INSERT_PLACEHOLDERS = ", ".join(["%s"] * 10)
    _BASE_INSERT_QUERY = f"INSERT INTO saved_posts ({_INSERT_COLUMNS}) VALUES ({_INSERT_PLACEHOLDERS})"

    async def delete_by_id(self, item_id: int, user_id: str) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM saved_posts WHERE item_id = %s AND user_id = %s",
                (item_id, user_id),
            )

    async def count_by_user_id(self, user_id: str) -> int:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                "SELECT COUNT(*) AS count FROM saved_posts WHERE user_id = %s",
                (user_id,),
            )
            row = await cursor.fetchone()
            return int(row["count"]) if row else 0

    async def create_processing_item(self, user_id: str, post_url: str) -> int:
        return await self._insert_item(
            user_id=user_id,
            source_url=post_url,
            category="PROCESSING",
            title="PROCESSING",
            price="분석 중...",
            brand=None,
            is_available=None,
            image_url="AI가 열심히 정보를 추출하고 있어요",
            image_vector=None,
            shop=None,
            return_id=True,
        )

    async def create_manual_item(
        self,
        user_id: str,
        source_url: str,
        category: str,
        title: str | None = None,
        image_url: str = "",
        image_vector: str | None = None,
        price: str | None = None,
        brand: str | None = None,
        is_available: str | None = None,
        shop: str | None = None,
    ) -> int:
        return await self._insert_item(
            user_id=user_id,
            source_url=source_url,
            category=category,
            title=title,
            price=price,
            brand=brand,
            is_available=is_available,
            image_url=image_url,
            image_vector=image_vector,
            shop=shop,
            return_id=True,
        )

    async def _insert_item(
        self,
        user_id: str,
        source_url: str,
        category: str,
        title: str | None,
        price: str | None,
        brand: str | None,
        is_available: str | None,
        image_url: str,
        image_vector: str | None,
        shop: str | None,
        return_id: bool = False,
    ) -> int | None:
        query = self._BASE_INSERT_QUERY
        if return_id:
            query = f"{query} RETURNING item_id"

        async with self.conn.cursor() as cursor:
            await cursor.execute(
                query,
                (
                    user_id,
                    source_url,
                    category,
                    title,
                    price,
                    brand,
                    is_available,
                    image_url,
                    image_vector,
                    shop,
                ),
            )
            item_id = None
            if return_id:
                row = await cursor.fetchone()
                item_id = int(row[0]) if row else None
            await self.conn.commit()
            return item_id

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("image_vector") is not None:
            item["image_vector"] = str(item["image_vector"])
        return item

    async def list_feed_items(self, user_id: str):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    item_id,
                    source_url,
                    title,
                    price,
                    brand,
                    category,
                    is_available,
                    image_url,
                    image_vector,
                    shop,
                    created_at
                FROM saved_posts
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            items = await cursor.fetchall()
            return jsonable_encoder([self._normalize_item(item) for item in items])
