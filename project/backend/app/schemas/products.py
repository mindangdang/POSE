from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from pydantic import BaseModel


class ProductDTO(BaseModel):
    product_id: int
    source_url: str
    title: str
    price: Decimal | None
    currency: str
    brand: str
    category: str
    is_soldout: bool | None
    image_url: str
    image_vector: str | None
    shop: str
    gender: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any]):
        values = dict(row)
        if values.get("image_vector") is not None:
            values["image_vector"] = str(values["image_vector"])
        return cls.model_validate(values)


class ProductListDTO(BaseModel):
    product_id: int
    source_url: str
    title: str
    title_vector: list[float] | None = None
    price: Decimal | None = None
    currency: str
    brand: str
    category: str
    is_soldout: bool | None = None
    image_url: str
    image_vector: list[float] | None = None
    shop_id: int
    gender: str
    created_at: datetime
    shop: str | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]):
        values = dict(row)
        if "product_id" not in values and "id" in values:
            values["product_id"] = values.pop("id")
        return cls.model_validate(values)


class ProductSearchDTO(ProductDTO):
    similarity: float | None = None
    search_source: str = "product_db"


class SavedProductDTO(ProductDTO):
    created_at: datetime
