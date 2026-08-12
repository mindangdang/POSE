from dataclasses import dataclass
from typing import Any
from project.backend.basic_functions.utils import _extract_vector_batch, _extract_text_vector_batch
from project.backend.basic_functions.crawlers.utils import text_translate, get_clean_category

@dataclass(slots=True)
class ProductDBRepository:
    conn: Any

    async def insert_items_batch(
        self,
        source_url: str,
        extracted_items: list[dict],
    ) -> None:
        """크롤링으로 추출된 여러 아이템을 한 번에 DB에 삽입합니다."""
        if not extracted_items:
            return
        try:
            async with self.conn.cursor() as cursor:
                insert_query_with_id = """
                    INSERT INTO product_db 
                    (item_id, source_url, title, price, brand, category, is_available, image_url, image_vector, shop, gender)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_url, title) DO NOTHING;
                """
                insert_query_without_id = """
                    INSERT INTO product_db 
                    (source_url, title, price, brand, category, is_available, image_url, image_vector, shop, gender)
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
                    title_vec = await _extract_text_vector_batch([text_translate(title, 'en')])
                    price = item.get("price")
                    brand = item.get("brand") or "UNKNOWN"
                    category = get_clean_category(title_vec[0]) if title_vec else "PRODUCT"
                    is_available = str(item.get("is_available", "Unknown"))
                    shop = item.get("shop") or "UNKNOWN"
                    image_url = item.get("image_url") or item.get("local_path") or ""
                    vector_list = await _extract_vector_batch(image_url)
                    vector_str = str(vector_list) if vector_list else None
                    gender = item.get("gender") or "UNKNOWN"

                    if item_id is not None:
                        batch_with_id.append((
                            item_id,
                            source_url,
                            title,
                            price,
                            brand,
                            category,
                            is_available,
                            image_url,
                            vector_str,
                            shop,
                            gender
                        ))
                    else:
                        batch_without_id.append((
                            source_url,
                            title,
                            price,
                            brand,
                            category,
                            is_available,
                            image_url,
                            vector_str,
                            shop,
                            gender
                        ))

                await cursor.executemany(insert_query_with_id, batch_with_id)
                if batch_without_id:
                    await cursor.executemany(insert_query_without_id, batch_without_id)
            print(f"DB 저장 완료: {len(extracted_items)}개 아이템")

        except Exception as e:
            print(f"DB 저장 중 에러 발생: {e}")
            raise e


    async def search_by_title_vector(
        self,
        query_vector: list[float],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """title_vector cosine similarity 기준으로 product_db 상품을 조회합니다."""
        if not query_vector:
            return []

        vector_str = str(query_vector)
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    item_id,
                    source_url,
                    title,
                    price,
                    brand,
                    category,
                    is_soldout AS is_available,
                    image_url,
                    image_vector,
                    shop,
                    gender,
                    1 - (title_vector <=> %s::vector) AS similarity
                FROM product_db
                WHERE title_vector IS NOT NULL
                ORDER BY title_vector <=> %s::vector
                LIMIT %s;
                """,
                (vector_str, vector_str, limit),
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        results = []
        for row in rows:
            item = self._normalize_item(dict(zip(columns, row)))
            item["item_id"] = str(item.get("item_id"))
            item["likes"] = None
            item["dislikes"] = None
            item["search_source"] = "product_db"
            results.append(item)
        return results

    async def search_by_title_text(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """title 텍스트가 일치하거나 유사한 product_db 상품을 조회합니다."""
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        like_query = f"%{normalized_query}%"
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    item_id,
                    source_url,
                    title,
                    price,
                    brand,
                    category,
                    is_soldout AS is_available,
                    image_url,
                    image_vector,
                    shop,
                    gender,
                    CASE
                        WHEN lower(title) = lower(%s) THEN 0
                        WHEN lower(title) LIKE lower(%s) || '%%' THEN 1
                        WHEN lower(title) LIKE '%%' || lower(%s) || '%%' THEN 2
                        ELSE 3
                    END AS text_rank
                FROM product_db
                WHERE lower(title) LIKE lower(%s)
                ORDER BY text_rank, created_at DESC
                LIMIT %s;
                """,
                (normalized_query, normalized_query, normalized_query, like_query, limit),
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        results = []
        for row in rows:
            item = self._normalize_item(dict(zip(columns, row)))
            item["item_id"] = str(item.get("item_id"))
            item["likes"] = None
            item["dislikes"] = None
            item["search_source"] = "product_db"
            results.append(item)
        return results

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("image_vector") is not None:
            item["image_vector"] = str(item["image_vector"])
        return item

 