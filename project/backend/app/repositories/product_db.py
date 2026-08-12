from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from project.backend.basic_functions.utils import _extract_vector_sync


@dataclass(slots=True)
class ProductDBRepository:
    conn: Any

    _SHOP_ALIASES = {
        "fruitsfamily": "FRUITS FAMILY",
        "fruits family": "FRUITS FAMILY",
        "fetching": "FETCHING",
        "empty": "EMPTY",
        "worksout": "WORKSOUT",
        "8division": "8DIVISION",
        "iamshop": "IAMSHOP",
        "thebounce": "THE BOUNCE",
        "the bounce": "THE BOUNCE",
        "thexshop": "THE X SHOP",
        "the x shop": "THE X SHOP",
        "collectiv": "COLLECTIV",
        "kream": "KREAM",
        "musinsa": "MUSINSA",
        "eql": "EQL",
        "29cm": "29CM",
        "bunjang": "Bunjang",
        "daangn": "Danggeun Market",
        "danggeun market": "Danggeun Market",
        "joongna": "Joonggonara",
        "joonggonara": "Joonggonara",
        "zara": "ZARA",
    }

    async def exists(self, product_id: int) -> bool:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT 1 FROM product_db WHERE id = %s",
                (product_id,),
            )
            return await cursor.fetchone() is not None

    async def insert_item(self, source_url: str, item: dict[str, Any]) -> int:
        image_url = item.get("image_url") or item.get("local_path") or ""
        vector_list = item.get("image_vector")
        if vector_list is None and image_url:
            vector_list = await _extract_vector_sync(image_url)
        vector_value = str(vector_list) if vector_list else None

        async with self.conn.cursor() as cursor:
            shop_name = self._canonical_shop_name(item.get("shop"))
            await cursor.execute(
                "SELECT id FROM shops WHERE name = %s",
                (shop_name,),
            )
            shop_row = await cursor.fetchone()
            if not shop_row:
                await cursor.execute("SELECT id FROM shops WHERE name = 'UNKNOWN'")
                shop_row = await cursor.fetchone()
            if not shop_row:
                raise RuntimeError("The required UNKNOWN shop seed is missing")
            shop_id = int(shop_row[0])

            await cursor.execute(
                """
                INSERT INTO product_db (
                    source_url, title, price, currency, brand, category, is_soldout,
                    image_url, image_vector, shop_id, gender
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO UPDATE SET
                    title = EXCLUDED.title,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    brand = EXCLUDED.brand,
                    category = EXCLUDED.category,
                    is_soldout = EXCLUDED.is_soldout,
                    image_url = EXCLUDED.image_url,
                    image_vector = COALESCE(EXCLUDED.image_vector, product_db.image_vector),
                    shop_id = EXCLUDED.shop_id,
                    gender = EXCLUDED.gender
                RETURNING id
                """,
                (
                    source_url,
                    item.get("title") or "Unknown",
                    self._get_price(item.get("price")),
                    self._get_currency(item.get("currency")),
                    item.get("brand") or "UNKNOWN",
                    item.get("category") or "PRODUCT",
                    self._get_is_soldout(item),
                    image_url,
                    vector_value,
                    shop_id,
                    item.get("gender") or "UNKNOWN",
                ),
            )
            row = await cursor.fetchone()
        if not row:
            raise RuntimeError("Product insert did not return an id")
        return int(row[0])

    async def insert_items_batch(
        self,
        source_url: str,
        extracted_items: list[dict[str, Any]],
    ) -> list[int]:
        product_ids = []
        for item in extracted_items:
            product_ids.append(
                await self.insert_item(item.get("source_url") or source_url, item)
            )
        return product_ids

    async def search_by_title_vector(
        self,
        query_vector: list[float],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not query_vector:
            return []

        vector_str = str(query_vector)
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    p.id AS product_id, source_url, title, price, currency, brand, category,
                    is_soldout, image_url, image_vector, s.name AS shop, gender,
                    1 - (title_vector <=> %s::vector) AS similarity
                FROM product_db AS p
                JOIN shops AS s ON s.id = p.shop_id
                WHERE title_vector IS NOT NULL
                ORDER BY p.title_vector <=> %s::vector
                LIMIT %s
                """,
                (vector_str, vector_str, limit),
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        return [self._normalize_search_item(dict(zip(columns, row))) for row in rows]

    async def search_by_title_text(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        like_query = f"%{normalized_query}%"
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    p.id AS product_id, source_url, title, price, currency, brand, category,
                    is_soldout, image_url, image_vector, s.name AS shop, gender,
                    CASE
                        WHEN lower(title) = lower(%s) THEN 0
                        WHEN lower(title) LIKE lower(%s) || '%%' THEN 1
                        WHEN lower(title) LIKE '%%' || lower(%s) || '%%' THEN 2
                        ELSE 3
                    END AS text_rank
                FROM product_db AS p
                JOIN shops AS s ON s.id = p.shop_id
                WHERE lower(title) LIKE lower(%s)
                ORDER BY text_rank, created_at DESC
                LIMIT %s
                """,
                (normalized_query, normalized_query, normalized_query, like_query, limit),
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        return [self._normalize_search_item(dict(zip(columns, row))) for row in rows]

    @staticmethod
    def _canonical_shop_name(value: Any) -> str:
        if not isinstance(value, str):
            return "UNKNOWN"
        normalized = value.strip().lower()
        return ProductDBRepository._SHOP_ALIASES.get(normalized, "UNKNOWN")

    @staticmethod
    def _get_currency(value: Any) -> str:
        if not isinstance(value, str):
            return "KRW"
        normalized = value.strip().upper()
        aliases = {"₩": "KRW", "KRW": "KRW", "$": "USD", "USD": "USD", "¥": "JPY", "JPY": "JPY", "€": "EUR", "EUR": "EUR"}
        if normalized in aliases:
            return aliases[normalized]
        return normalized if re.fullmatch(r"[A-Z]{3}", normalized) else "KRW"

    @staticmethod
    def _get_price(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)):
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None
        if not isinstance(value, str):
            return None

        normalized = value.strip().replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if not match:
            return None
        try:
            return Decimal(match.group())
        except InvalidOperation:
            return None

    @staticmethod
    def _get_is_soldout(item: dict[str, Any]) -> bool | None:
        if isinstance(item.get("is_soldout"), bool):
            return item["is_soldout"]
        return None

    @staticmethod
    def _normalize_search_item(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("image_vector") is not None:
            item["image_vector"] = str(item["image_vector"])
        item["product_id"] = str(item.get("product_id"))
        item["search_source"] = "product_db"
        return item
