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


class FeedbackRequest(BaseModel):
    user_id: str | int
    query: str
    result: str
    feedback_type: str
    reason: Optional[str] = ""


class ManualItemCreate(BaseModel):
    user_id: str | int
    category: str
    vibe: str
    facts: dict
    url: str
    image_url: Optional[str] = ""
