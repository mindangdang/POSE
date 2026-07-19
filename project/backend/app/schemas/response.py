from pydantic import BaseModel, Field
from typing import Optional, List

class Product(BaseModel):
    id: Optional[str] = Field(description="상품 고유 ID", default=None)
    title: Optional[str] = Field(description="상품명", default=None)
    price: Optional[str] = Field(description="상품가격", default=None)
    brand: Optional[str] = Field(description="브랜드명", default=None)
    category: Optional[str] = Field(description="'outer', 'top', 'bottom', 'shoes', 'accessories', 'jewelry'", default=None)
    is_available: Optional[str] = Field(description="구매 가능 여부", default=None)
    image_url: Optional[str] = Field(description="이미지 퍼블릭 url", default=None)
    image_vector: Optional[str] = Field(description="이미지 임베딩 벡터", default=None)
    shop: Optional[str] = Field(description="쇼핑몰 출처", default=None)
    source_url: Optional[str] = Field(description="상품 정보 출처 URL", default=None)

