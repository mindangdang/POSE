from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row


@dataclass(slots=True)
class SavedPostsRepository:
    conn: Any

    _JOINED_COLUMNS = """
        p.id AS product_id,
        p.source_url,
        p.title,
        p.price,
        p.currency,
        p.brand,
        p.category,
        p.is_soldout,
        p.image_url,
        p.image_vector,
        s.name AS shop,
        p.gender,
        sp.created_at
    """

    async def create(
        self,
        *,
        user_id: int,
        product_id: int,
    ) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (user_id, product_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, product_id) DO NOTHING
                """,
                (user_id, product_id),
            )

    async def insert_items_batch(
        self,
        *,
        user_id: int,
        product_ids: list[int],
    ) -> None:
        if not product_ids:
            return

        async with self.conn.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO saved_posts (user_id, product_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, product_id) DO NOTHING
                """,
                [(user_id, product_id) for product_id in product_ids],
            )

    async def delete_by_id(self, product_id: int, user_id: int) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM saved_posts WHERE product_id = %s AND user_id = %s",
                (product_id, user_id),
            )

    async def count_by_user_id(self, user_id: int) -> int:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                "SELECT COUNT(*) AS count FROM saved_posts WHERE user_id = %s",
                (user_id,),
            )
            row = await cursor.fetchone()
            return int(row["count"]) if row else 0

    async def list_feed_items(self, user_id: int) -> list[dict[str, Any]]:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT {self._JOINED_COLUMNS}
                FROM saved_posts AS sp
                JOIN product_db AS p ON p.id = sp.product_id
                JOIN shops AS s ON s.id = p.shop_id
                WHERE sp.user_id = %s
                ORDER BY sp.created_at DESC
                """,
                (user_id,),
            )
            items = await cursor.fetchall()
        return jsonable_encoder([self._normalize_item(item) for item in items])

    async def get_random_feed_item(self, user_id: int) -> dict[str, Any] | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT {self._JOINED_COLUMNS}
                FROM saved_posts AS sp
                JOIN product_db AS p ON p.id = sp.product_id
                JOIN shops AS s ON s.id = p.shop_id
                WHERE sp.user_id = %s
                ORDER BY RANDOM()
                LIMIT 1
                """,
                (user_id,),
            )
            item = await cursor.fetchone()
        return jsonable_encoder(self._normalize_item(item)) if item else None

    async def _get_joined_item(
        self,
        *,
        product_id: int,
        user_id: int,
    ) -> dict[str, Any] | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT {self._JOINED_COLUMNS}
                FROM saved_posts AS sp
                JOIN product_db AS p ON p.id = sp.product_id
                JOIN shops AS s ON s.id = p.shop_id
                WHERE sp.product_id = %s AND sp.user_id = %s
                """,
                (product_id, user_id),
            )
            item = await cursor.fetchone()
        return jsonable_encoder(self._normalize_item(item)) if item else None

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        if normalized.get("image_vector") is not None:
            normalized["image_vector"] = str(normalized["image_vector"])
        return normalized
