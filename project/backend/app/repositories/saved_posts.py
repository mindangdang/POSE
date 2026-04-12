import json
from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row


@dataclass(slots=True)
class SavedPostsRepository:
    conn: Any

    async def delete_by_id(self, item_id: int) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM saved_posts WHERE id = %s", (item_id,))

    async def create_processing_item(self, user_id: str, post_url: str) -> int:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (user_id, source_url, category, title, recommend, image_url, facts)
                VALUES (%s, %s, 'PROCESSING ', '분석 중...', 'AI가 열심히 바이브를 추출하고 있어요', '', '{}')
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
        recommend: str,
        facts: dict,
        image_url: str = "",
    ) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (user_id, source_url, category, recommend, facts, title, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    url,
                    category,
                    recommend,
                    json.dumps(facts),
                    facts.get("title", "Manual Item"),
                    image_url,
                ),
            )
            await self.conn.commit()

    async def list_feed_items(self, user_id: str):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    id,
                    source_url as url,
                    category,
                    facts,
                    recommend as recommend,
                    image_url,
                    summary_text,
                    created_at
                FROM saved_posts
                WHERE user_id = %s OR user_id = 'default_user'
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            items = await cursor.fetchall()
            return jsonable_encoder(items)
