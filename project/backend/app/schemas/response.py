from pydantic import BaseModel, Field
from typing import Optional, List

class Product(BaseModel):
    title: Optional[str] = Field(description="상품명", default=None)
    price: Optional[str] = Field(description="상품가격", default=None)
    brand: Optional[str] = Field(description="브랜드명", default=None)
    category: Optional[str] = Field(description="아우터,자켓,상의,하의,신발,악세서리 중 택1", default=None)
    is_available: Optional[str] = Field(description="구매 가능 여부", default=None)
    image_url: Optional[str] = Field(description="이미지 퍼블릭 url", default=None)
    image_vector: Optional[str] = Field(description="이미지 임베딩 벡터", default=None)
    shop: Optional[str] = Field(description="쇼핑몰 출처", default=None)

class TasteProfileResult(BaseModel):
    persona: str = Field(description="유저의 취향과 페르소나를 한 문장으로 정의하는 타이틀")
    unconscious_taste: str = Field(description="유저의 무의식적인 취향을 분석하는 텍스트 (2~3문장)")
    recommendation: str = Field(description="유저의 취향에 정합하는 새로운 키워드 제시 및 실존하는 장소/물건 추천")