from pydantic import BaseModel
from typing import List,Optional


class EmbedRequest(BaseModel):
    image_url: str

class EncodeTextRequest(BaseModel):
    text: str

class EmbedBatchRequest(BaseModel):
    image_urls: List[Optional[str]]

class EncodeTextBatchRequest(BaseModel):
    texts: List[str]
