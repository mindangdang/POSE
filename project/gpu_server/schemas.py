from pydantic import BaseModel

class EmbedRequest(BaseModel):
    image_url: str
    category: str

class TasteVectorRequest(BaseModel):
    image_vectors: list[list[float]]

class EncodeTextRequest(BaseModel):
    text: str

class EvaluateRequest(BaseModel):
    item: dict
    user_taste_profile: dict
    query_vector: list[list[float]]
    semantic_thresh: float = 0.10
    aesthetic_thresh: float = 0.0