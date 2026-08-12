import os
from PIL import Image
import io
import asyncio
import httpx
from fastapi import APIRouter
from project.gpu_server.embedding_reranking import FashionSiglipReRankingPipeline
from project.gpu_server.schemas import *
from project.backend.app.manage.settings import IMAGE_DIR
    
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
                    vec = pipeline.get_image_vector(img)
                    return {"vector": vec}
        else:
            local_path = os.path.join(str(IMAGE_DIR), os.path.basename(image_url))
            if os.path.exists(local_path):
                with Image.open(local_path) as img:
                    vec = pipeline.get_image_vector(img)
                    return {"vector": vec}
                
    except Exception as e:
        print(f"벡터 추출 에러: {e}")
    return {"vector": None}

@router.post("/encode_text")
async def encode_text(request: EncodeTextRequest):
    try:
        pipeline = get_pipeline()
        return {"vector": pipeline.encode_text(request.text).cpu().tolist()}
    except Exception as e:
        print(f"텍스트 인코딩 에러: {e}")
    return {"vector": None}

###############################################################################################################

@router.post("/embedding_batch")
async def embed_image_batch(request: EmbedBatchRequest):
    pipeline = get_pipeline()
    
    # 단일 이미지 비동기 다운로드 및 로드 함수
    async def _fetch_and_load(client, url):
        if not url:
            return None
        try:
            if url.startswith(('http://', 'https://')):
                resp = await client.get(url, timeout=12.0, follow_redirects=True)
                resp.raise_for_status()
                return Image.open(io.BytesIO(resp.content))
            else:
                local_path = os.path.join(str(IMAGE_DIR), os.path.basename(url))
                if os.path.exists(local_path):
                    return Image.open(local_path)
        except Exception as e:
            print(f"이미지 로드 에러 ({url}): {e}")
        return None

    try:
        # 1. 여러 이미지를 동시에 다운로드 (네트워크 I/O 병렬화)
        async with httpx.AsyncClient() as client:
            tasks = [_fetch_and_load(client, url) for url in request.image_urls]
            images = await asyncio.gather(*tasks)

        # 2. None이 아닌 유효한 이미지 필터링 및 원본 인덱스 추적
        valid_images = []
        valid_indices = []
        for idx, img in enumerate(images):
            if img is not None:
                valid_images.append(img)
                valid_indices.append(idx)

        # 3. 배치 벡터 추출 (CPU/GPU 블로킹 연산이므로 스레드 풀로 오프로딩)
        valid_vectors = []
        if valid_images:
            valid_vectors = await asyncio.to_thread(pipeline.get_image_vectors, valid_images)

        # 4. 원본 요청 순서에 맞게 결과 배열 재구성
        # 반환 배열을 None으로 초기화한 뒤 추출 성공한 벡터만 제자리에 삽입
        final_vectors = [None] * len(request.image_urls)
        for vec, original_idx in zip(valid_vectors, valid_indices):
            final_vectors[original_idx] = vec
                
        return {"vectors": final_vectors}

    except Exception as e:
        print(f"전체 벡터 추출 에러: {e}")
        return {"vectors": [None] * len(request.image_urls)}

@router.post("/encode_text_batch")
async def encode_text_batch(request: EncodeTextBatchRequest):
    try:
        pipeline = get_pipeline()
        encoded = await asyncio.to_thread(pipeline.encode_texts, request.texts)
        
        if hasattr(encoded, "cpu"):
            vectors = encoded.cpu().tolist()
        else:
            vectors = encoded
            
        return {"vectors": vectors}
    
    except Exception as e:
        print(f"텍스트 인코딩 에러: {e}")
        return {"vectors": [None] * len(request.texts)}