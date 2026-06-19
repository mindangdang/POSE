import json
from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row


@dataclass(slots=True)
class SavedPostsRepository:
    conn: Any

    async def delete_by_id(self, item_id: int, user_id: str) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM saved_posts WHERE id = %s AND user_id = %s", (item_id, user_id))

    async def create_processing_item(self, user_id: str, post_url: str) -> int:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (
                    user_id,
                    source_url,
                    category,
                    title,
                    price,
                    brand,
                    is_available,
                    image_url,
                    shop
                )
                VALUES (%s, %s, 'PROCESSING', 'PROCESSING', '분석 중...', NULL, NULL, 'AI가 열심히 정보를 추출하고 있어요', NULL)
                RETURNING id
                """,
                (user_id, post_url),
            )
            new_item_id = (await cursor.fetchone())[0]
            await self.conn.commit()
            return new_item_id

    async def count_by_user_id(self, user_id: str) -> int:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT COUNT(*) AS count FROM saved_posts WHERE user_id = %s", (user_id,))
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def create_manual_item(
        self,
        user_id: str,
        url: str,
        category: str,
        image_url: str = "",
        image_vector: str | None = None,
        price: str | None = None,
        brand: str | None = None,
        is_available: str | None = None,
        shop: str | None = None,
    ) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (
                    user_id,
                    source_url,
                    category,
                    title,
                    price,
                    brand,
                    is_available,
                    image_url,
                    image_vector,
                    shop
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    url,
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
            await self.conn.commit()

    async def create_item(
        self,
        user_id: str,
        url: str,
        category: str,
        title: str = "",
        image_url: str = "",
        image_vector: str | None = None,
        price: str | None = None,
        brand: str | None = None,
        is_available: str | None = None,
        shop: str | None = None,
    ) -> int:
        """
        상품 아이템을 생성하고 ID를 반환합니다.
        """
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (
                    user_id,
                    source_url,
                    category,
                    title,
                    price,
                    brand,
                    is_available,
                    image_url,
                    image_vector,
                    shop
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    url,
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
            item_id = (await cursor.fetchone())[0]
            return item_id

    async def list_feed_items(self, user_id: str):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    id,
                    source_url as url,
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
            normalized_items = []
            for item in items:
                if item.get("image_vector") is not None:
                    item["image_vector"] = str(item["image_vector"])
                normalized_items.append(item)
            return jsonable_encoder(normalized_items)
