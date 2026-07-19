from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class UrlAnalyzeRequest(BaseModel):
    url: str


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
    url: str
    image_url: Optional[str] = ""
    title: Optional[str] = None
    price: Optional[str] = None
    brand: Optional[str] = None
    is_available: Optional[str] = None
    shop: Optional[str] = None


class EventCreate(BaseModel):
    timestamp: datetime
    event_name: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    user_id: str | int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    page: str | None = Field(default=None, max_length=500)
    user_agent: str | None = Field(default=None, max_length=1000)


class EventBatchCreate(BaseModel):
    events: list[EventCreate] = Field(min_length=1, max_length=20)
