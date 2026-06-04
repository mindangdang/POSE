from pydantic import BaseModel

class EmbedRequest(BaseModel):
    image_url: str
    category: str

class TasteVectorRequest(BaseModel):
    image_vectors: list[list[float]]

class EncodeTextRequest(BaseModel):
    text: str

