from dataclasses import dataclass
from typing import Any
import asyncio
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row
from project.backend.app.db.utils import _extract_vector_sync


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
        '''크롤링 요청시 임시 아이템을 생성하여 DB에 저장하고 item_id를 생성하여 반환하는 메서드입니다.'''

        return await self._insert_item(
            item_id=None,
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
        item_id: int | None,
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
        '''검색결과 아이템을 피드에 저장하기 위한 메서드입니다.'''
        return await self._insert_item(
            item_id=item_id,
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
            return_id=False,
        )

    async def _insert_item(
        self,
        item_id: int | None,
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
        '''DB에 아이템을 삽입하고 item_id를 반환하는 공통 메서드입니다.'''
        
        query = self._BASE_INSERT_QUERY
        if return_id:
            query = f"{query} RETURNING item_id"

        async with self.conn.cursor() as cursor:
            await cursor.execute(
                query,
                (
                    item_id,
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
            new_item_id = None
            if return_id:
                row = await cursor.fetchone()
                new_item_id = int(row[0]) if row else None
            await self.conn.commit()
            return new_item_id

    async def insert_items_batch(
        self,
        user_id: str,
        source_url: str,
        extracted_items: list[dict],
    ) -> None:
        """크롤링으로 추출된 여러 아이템을 한 번에 DB에 삽입합니다."""
        if not extracted_items:
            return

        try:
            async with self.conn.cursor() as cursor:
                insert_query_with_id = """
                    INSERT INTO saved_posts 
                    (item_id, user_id, source_url, title, price, brand, category, is_available, image_url, image_vector, shop)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_url, title) DO NOTHING;
                """
                insert_query_without_id = """
                    INSERT INTO saved_posts 
                    (user_id, source_url, title, price, brand, category, is_available, image_url, image_vector, shop)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_url, title) DO NOTHING;
                """
                batch_with_id = []
                batch_without_id = []

                for item in extracted_items:
                    raw_item_id = item.get("item_id")
                    item_id = None
                    if raw_item_id is not None:
                        try:
                            item_id = int(raw_item_id)
                        except (TypeError, ValueError):
                            item_id = None

                    title = item.get("title", "Unknown")
                    price = item.get("price")
                    brand = item.get("brand") or "UNKNOWN"
                    category = item.get("category") or "PRODUCT"
                    is_available = str(item.get("is_available", "Unknown"))
                    shop = item.get("shop") or "UNKNOWN"
                    image_url = item.get("image_url") or item.get("local_path") or ""
                    vector_list = await _extract_vector_sync(image_url)
                    vector_str = str(vector_list) if vector_list else None

                    if item_id is not None:
                        batch_with_id.append((
                            item_id,
                            str(user_id),
                            source_url,
                            title,
                            price,
                            brand,
                            category,
                            is_available,
                            image_url,
                            vector_str,
                            shop,
                        ))
                    else:
                        batch_without_id.append((
                            str(user_id),
                            source_url,
                            title,
                            price,
                            brand,
                            category,
                            is_available,
                            image_url,
                            vector_str,
                            shop,
                        ))

                if batch_with_id:
                    await cursor.executemany(insert_query_with_id, batch_with_id)
                if batch_without_id:
                    await cursor.executemany(insert_query_without_id, batch_without_id)

            print(f"DB 저장 완료: {len(extracted_items)}개 아이템")
        except Exception as e:
            print(f"DB 저장 중 에러 발생: {e}")
            raise e

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
