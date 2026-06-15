import os
from PIL import Image
import io
import httpx
from fastapi import APIRouter
from project.gpu_server.embedding_reranking import FashionSiglipReRankingPipeline
from project.gpu_server.schemas import EmbedRequest, TasteVectorRequest, EncodeTextRequest
from project.backend.app.utils.settings import IMAGE_DIR
    
router = APIRouter()

def get_pipeline():
    return FashionSiglipReRankingPipeline()

@router.post("/embedding")
async def embed_image(request: EmbedRequest):
    try:
        pipeline = get_pipeline()
        image_url = request.image_url
        if not image_url:
            return {"vector": None}
            
        if image_url.startswith(('http://', 'https://')):
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=12.0, follow_redirects=True)
                resp.raise_for_status()
                with Image.open(io.BytesIO(resp.content)) as img:
                    vec = pipeline.get_image_vector(img, request.category)
                    return {"vector": vec}
        else:
            local_path = os.path.join(str(IMAGE_DIR), os.path.basename(image_url))
            if os.path.exists(local_path):
                with Image.open(local_path) as img:
                    vec = pipeline.get_image_vector(img, request.category)
                    return {"vector": vec}
    except Exception as e:
        print(f"벡터 추출 에러: {e}")
    return {"vector": None}

@router.post("/build_taste_vector")
async def build_taste_vector(request: TasteVectorRequest):
    try:
        pipeline = get_pipeline()
        taste_profile = pipeline.build_user_taste_vector(request.image_vectors)
        if taste_profile is not None:
            return {
                "vector": {
                    "consensus": taste_profile["consensus"].cpu().tolist(),
                    "memory": taste_profile["memory"].cpu().tolist()
                }
            }
    except Exception as e:
        print(f"취향 벡터 합성 에러: {e}")
    return {"vector": None}

@router.post("/encode_text")
async def encode_text(request: EncodeTextRequest):
    try:
        pipeline = get_pipeline()
        return {"vector": pipeline.encode_text(request.text).cpu().tolist()}
    except Exception as e:
        print(f"텍스트 인코딩 에러: {e}")
    return {"vector": None}
