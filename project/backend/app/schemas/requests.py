from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


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
    source_url: Optional[str] = None
    image_url: Optional[str] = ""
    title: Optional[str] = None
    price: Optional[str] = None
    brand: Optional[str] = None
    is_available: Optional[str] = None
    shop: Optional[str] = None


class VoteRequest(BaseModel):
    direction: Literal["like", "dislike"]


class EventLogCreate(BaseModel):
    action: Literal[
        "SEARCH",
        "LIKE",
        "DISLIKE",
        "SAVE_WISHLIST",
        "REMOVE_WISHLIST",
        "CLICK_PURCHASE",
        "CLICK_ITEM",
        "VOTE_PRETTY",
        "VOTE_UGLY",
    ]
    entity_type: Literal["SEARCH_RESULT", "VOTING_ITEM", "WISHLIST_ITEM", "SITE"]
    entity_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
