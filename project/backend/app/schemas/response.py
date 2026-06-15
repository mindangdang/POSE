from pydantic import BaseModel, Field
from typing import Optional, List


class ProductAnalysisResult(BaseModel):
    recommend: str = Field(description="어떤 사람에게 추천하는지 설명+대상에 대한 큐레이팅")
    key_details: List[str] = Field(description="핵심 특징 1, 2, 3")
    sub_category: Optional[str] = Field(description="Choose 1 from Outerwear, Jacket, Top, Bottom, Jewelry, Accessories, or Shoes", default=None)

class Facts(BaseModel):
    title: Optional[str] = Field(description="상품명, 브랜드명, 작품명, 상호명 또는 주제, 제목", default=None)
    price_info: Optional[str] = Field(description="상품가격, 메뉴 가격대 등 비용 관련 텍스트", default=None)
    location_text: Optional[str] = Field(description="위치, 주소 텍스트", default=None)
    time_info: Optional[str] = Field(description="시간/기간 텍스트", default=None)
    key_details: Optional[List[str]] = Field(description="핵심 특징 1, 2, 3", default=None)

class ExtractedItem(BaseModel):
    image_index: int = Field(description="이 대상이 가장 잘 나타난 슬라이드의 인덱스 (첫 번째 사진은 0)") 
    category: str = Field(description="PLACE, PRODUCT, MEDIA, TIP, INSPIRATION 중 택 1")
    sub_category: Optional[str] = Field(description="Choose 1 from Outerwear, Jacket, Top, Bottom, Jewelry, Accessories, or Shoes", default=None)
    recommend: str = Field(description="어떤 사람에게 추천하는지 설명+대상에 대한 큐레이팅")
    facts: Facts

class InstaAnalysisResult(BaseModel):
    extracted_items: List[ExtractedItem]

class TasteProfileResult(BaseModel):
    persona: str = Field(description="유저의 취향과 페르소나를 한 문장으로 정의하는 타이틀")
    unconscious_taste: str = Field(description="유저의 무의식적인 취향을 분석하는 텍스트 (2~3문장)")
    recommendation: str = Field(description="유저의 취향에 정합하는 새로운 키워드 제시 및 실존하는 장소/물건 추천")