from typing import Optional

from pydantic import BaseModel


class UrlAnalyzeRequest(BaseModel):
    url: str
    session_id: Optional[str] = None


class TasteUpdate(BaseModel):
    summary: str


class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = 1
    user_id: int | str | None = None
    domain_map: Optional[dict[str, str]] = None 


class ManualItemCreate(BaseModel):
    user_id: str | int
    category: str
    sub_category: str
    recommend: str
    facts: dict
    url: str
    image_url: Optional[str] = ""

class GoogleAuthRequest(BaseModel):
    access_token: str