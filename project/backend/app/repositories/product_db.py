from dataclasses import dataclass
from typing import Any
from project.backend.basic_functions.utils import _extract_vector_sync


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
                    price = item.get("price")
                    brand = item.get("brand") or "UNKNOWN"
                    category = item.get("category") or "PRODUCT"
                    is_available = str(item.get("is_available", "Unknown"))
                    shop = item.get("shop") or "UNKNOWN"
                    image_url = item.get("image_url") or item.get("local_path") or ""
                    vector_list = await _extract_vector_sync(image_url)
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

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("image_vector") is not None:
            item["image_vector"] = str(item["image_vector"])
        return item

 