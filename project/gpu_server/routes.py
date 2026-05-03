import os
from PIL import Image
import io
import httpx
from fastapi import FastAPI
from project.embedding.embedding_reranking import FashionSiglipReRankingPipeline
from project.embedding.schemas import EmbedRequest, TasteVectorRequest, EncodeTextRequest, EvaluateRequest
from project.backend.app.core.settings import IMAGE_DIR
import torch
from project.backend.app.core.settings import load_backend_env, IMAGE_DIR
    
app = FastAPI(title="SigLIP Inference Server")
pipeline = FashionSiglipReRankingPipeline()

@app.post("/embedding")
async def embed_image(request: EmbedRequest):
    try:
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

@app.post("/build_taste_vector")
async def build_taste_vector(request: TasteVectorRequest):
    try:
        taste_vector = pipeline.build_user_taste_vector(request.image_vectors)
        if taste_vector is not None:
            return {"vector": taste_vector.cpu().tolist()}
    except Exception as e:
        print(f"취향 벡터 합성 에러: {e}")
    return {"vector": None}

@app.post("/encode_text")
async def encode_text(request: EncodeTextRequest):
    try:
        return {"vector": pipeline.encode_text(request.text).cpu().tolist()}
    except Exception as e:
        print(f"텍스트 인코딩 에러: {e}")
    return {"vector": None}

@app.post("/evaluate_single_item")
async def evaluate_single_item_endpoint(request: EvaluateRequest):
    try:
        user_taste_tensor = torch.tensor(request.user_taste_vector, device=pipeline.device)
        query_tensor = torch.tensor(request.query_vector, device=pipeline.device)
        
        item = request.item
        image_url = item.get("image_url")
        if not image_url:
            return {"result": None}
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url, headers=headers, timeout=12.0, follow_redirects=True)
            resp.raise_for_status()
            
            def _load_image():
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
            
            import asyncio
            raw_img = await asyncio.to_thread(_load_image)
            
        item["image_obj"] = raw_img
        
        result = pipeline.evaluate_single_item(
            item, 
            user_taste_tensor, 
            query_tensor, 
            request.semantic_thresh, 
            request.aesthetic_thresh
        )
        return {"result": result}
    except Exception as e:
        print(f"단일 아이템 평가 에러: {e}")
        return {"result": None}