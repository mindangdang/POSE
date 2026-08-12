from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from project.backend.app.db.models.product import Product
from project.backend.app.db.models.shop import Shop
from project.backend.basic_functions.utils import _extract_vector_sync


@dataclass(slots=True)
class ProductDBRepository:
    session: AsyncSession

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

    @staticmethod
    def _columns():
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
        )

    async def exists(self, product_id: int) -> bool:
        return await self.session.get(Product, product_id) is not None

    async def _shop_id(self, shop_value: Any) -> int:
        shop_name = self._canonical_shop_name(shop_value)
        shop_id = await self.session.scalar(select(Shop.id).where(Shop.name == shop_name))
        if shop_id is None:
            shop_id = await self.session.scalar(
                select(Shop.id).where(Shop.name == "UNKNOWN")
            )
        if shop_id is None:
            raise RuntimeError("The required UNKNOWN shop seed is missing")
        return int(shop_id)

    async def insert_item(self, source_url: str, item: dict[str, Any]) -> int:
        image_url = item.get("image_url") or item.get("local_path") or ""
        vector_value = item.get("image_vector")
        if vector_value is None and image_url:
            vector_value = await _extract_vector_sync(image_url)

        values = {
            "source_url": source_url,
            "title": item.get("title") or "Unknown",
            "price": self._get_price(item.get("price")),
            "currency": self._get_currency(item.get("currency")),
            "brand": item.get("brand") or "UNKNOWN",
            "category": item.get("category") or "PRODUCT",
            "is_soldout": self._get_is_soldout(item),
            "image_url": image_url,
            "image_vector": vector_value,
            "shop_id": await self._shop_id(item.get("shop")),
            "gender": item.get("gender") or "UNKNOWN",
        }
        excluded = insert(Product).excluded
        statement = (
            insert(Product)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[Product.source_url],
                set_={
                    "title": excluded.title,
                    "price": excluded.price,
                    "currency": excluded.currency,
                    "brand": excluded.brand,
                    "category": excluded.category,
                    "is_soldout": excluded.is_soldout,
                    "image_url": excluded.image_url,
                    "image_vector": func.coalesce(
                        excluded.image_vector, Product.image_vector
                    ),
                    "shop_id": excluded.shop_id,
                    "gender": excluded.gender,
                },
            )
            .returning(Product.id)
        )
        return int((await self.session.scalars(statement)).one())

    async def insert_items_batch(
        self,
        source_url: str,
        extracted_items: list[dict[str, Any]],
    ) -> list[int]:
        return [
            await self.insert_item(item.get("source_url") or source_url, item)
            for item in extracted_items
        ]

    async def search_by_title_vector(
        self,
        query_vector: list[float],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not query_vector:
            return []
        distance = Product.title_vector.cosine_distance(query_vector)
        statement = (
            select(*self._columns(), (1 - distance).label("similarity"))
            .join(Shop, Shop.id == Product.shop_id)
            .where(Product.title_vector.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).mappings().all()
        return [self._normalize_search_item(row) for row in rows]

    async def search_by_title_text(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []
        lowered_title = func.lower(Product.title)
        lowered_query = normalized_query.lower()
        text_rank = case(
            (lowered_title == lowered_query, 0),
            (lowered_title.like(f"{lowered_query}%"), 1),
            (lowered_title.like(f"%{lowered_query}%"), 2),
            else_=3,
        ).label("text_rank")
        statement = (
            select(*self._columns(), text_rank)
            .join(Shop, Shop.id == Product.shop_id)
            .where(lowered_title.like(f"%{lowered_query}%"))
            .order_by(text_rank, Product.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).mappings().all()
        return [self._normalize_search_item(row) for row in rows]

    @staticmethod
    def _canonical_shop_name(value: Any) -> str:
        if not isinstance(value, str):
            return "UNKNOWN"
        return ProductDBRepository._SHOP_ALIASES.get(value.strip().lower(), "UNKNOWN")

    @staticmethod
    def _get_currency(value: Any) -> str:
        if not isinstance(value, str):
            return "KRW"
        normalized = value.strip().upper()
        aliases = {
            "₩": "KRW", "KRW": "KRW", "$": "USD", "USD": "USD",
            "¥": "JPY", "JPY": "JPY", "€": "EUR", "EUR": "EUR",
        }
        return aliases.get(
            normalized,
            normalized if re.fullmatch(r"[A-Z]{3}", normalized) else "KRW",
        )

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
        match = re.search(r"-?\d+(?:\.\d+)?", value.strip().replace(",", ""))
        if not match:
            return None
        try:
            return Decimal(match.group())
        except InvalidOperation:
            return None

    @staticmethod
    def _get_is_soldout(item: dict[str, Any]) -> bool | None:
        value = item.get("is_soldout")
        return value if isinstance(value, bool) else None

    @staticmethod
    def _normalize_search_item(item: Any) -> dict[str, Any]:
        normalized = dict(item)
        if normalized.get("image_vector") is not None:
            normalized["image_vector"] = str(normalized["image_vector"])
        normalized["search_source"] = "product_db"
        return normalized
