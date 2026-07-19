from typing import Optional
from pydantic import BaseModel


class UrlAnalyzeRequest(BaseModel):
    url: str

class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = 1
    user_id: int | str | None = None
    domain_map: Optional[dict[str, str]] = None 


class ManualItemCreate(BaseModel):
    user_id: str | int
    category: str
    url: str
    image_url: Optional[str] = ""
    title: Optional[str] = None
    price: Optional[str] = None
    brand: Optional[str] = None
    is_available: Optional[str] = None
    shop: Optional[str] = None
