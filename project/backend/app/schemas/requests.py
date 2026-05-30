from typing import Optional

from pydantic import BaseModel,Field


class UrlAnalyzeRequest(BaseModel):
    url: str
    session_id: Optional[str] = None


class TasteUpdate(BaseModel):
    summary: str


class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = 1
    user_id: int | str | None = None

class FeedbackRequest(BaseModel):
    user_id: str | int
    query: str
    result: str
    feedback_type: str
    reason: Optional[str] = ""


class ManualItemCreate(BaseModel):
    user_id: str | int
    category: str
    sub_category: str
    recommend: str
    facts: dict
    url: str
    image_url: Optional[str] = ""


class ExtensionProductImport(BaseModel):
    """Extension에서 보내는 상품 정보"""
    url: str
    title: str
    image_url: str
    description: Optional[str] = ""
    brand: Optional[str] = ""
    price: Optional[str] = None
    currency: Optional[str] = "KRW"
    source: Optional[str] = "extension_content_script"
