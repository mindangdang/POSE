import os
import asyncio
import httpx
import numpy as np
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from project.backend.app.core.settings import load_backend_env
from project.backend.app.core.resilience import with_llm_resilience

load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        base_url=my_proxy_url
    )
)
MODEL_NAME = "gemini-embedding-2-preview"

async def fetch_image(url: str, client: httpx.AsyncClient) -> Image.Image | None:
    """비동기로 단일 썸네일 이미지를 다운로드하여 PIL 객체로 반환"""
    try:
        response = await client.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception:
        return None

@with_llm_resilience(fallback_default=lambda user_vibe_text, search_results: search_results)
async def rerank_with_gemini_embedding(user_vibe_text: str, search_results: list[dict]) -> list[dict]:
    """검색 결과를 Gemini Embedding을 사용해 이미지 무드 기반으로 재정렬"""
    if not search_results:
        return []

    print(f"[Gemini Embedding] {len(search_results)}개 썸네일 이미지 병렬 다운로드 시작...")
    
    # 2. 50개 썸네일 병렬 다운로드 (네트워크 I/O 최적화)
    valid_items = [item for item in search_results if item.get("image_url")]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        tasks = [fetch_image(item["image_url"], client) for item in valid_items]
        images = await asyncio.gather(*tasks)

    # 다운로드 실패한 이미지 필터링
    batch_images = []
    batch_items = []
    for img, item in zip(images, valid_items):
        if img:
            batch_images.append(img)
            batch_items.append(item)

    if not batch_images:
        return search_results

    print("[Gemini Embedding] 텍스트 및 이미지 벡터화 및 유사도 계산 중...")

    # 3. 유저 텍스트 임베딩 추출
    text_response = await client.aio.models.embed_content(
        model=MODEL_NAME,
        contents=user_vibe_text,
    )
    text_embeds = np.array([text_response.embeddings[0].values])

    # 4. 이미지 임베딩 병렬 추출
    @with_llm_resilience(fallback_default=None)
    async def embed_image(img):
        res = await client.aio.models.embed_content(
            model=MODEL_NAME,
            contents=img,
        )
        return res.embeddings[0].values

    embed_tasks = [embed_image(img) for img in batch_images]
    image_embeds_results = await asyncio.gather(*embed_tasks)

    final_items = []
    valid_image_embeds = []
    
    for item, emb in zip(batch_items, image_embeds_results):
        if emb is not None:
            final_items.append(item)
            valid_image_embeds.append(emb)

    if not valid_image_embeds:
        return search_results

    image_embeds = np.array(valid_image_embeds)

    # 정규화(Normalization)
    image_embeds = image_embeds / np.linalg.norm(image_embeds, axis=1, keepdims=True)
    text_embeds = text_embeds / np.linalg.norm(text_embeds, axis=1, keepdims=True)

    # 5. 코사인 유사도 계산 (행렬 곱셈)
    # 50개 이미지 각각이 텍스트(유저 취향)와 얼마나 일치하는지 점수(0~1) 산출
    similarities = np.dot(image_embeds, text_embeds.T).flatten()

    # 결과를 아이템 객체에 주입
    for item, score in zip(final_items, similarities):
        item["vibe_score"] = float(score)

    # 최종 점수 기준 내림차순 정렬
    reranked = sorted(final_items, key=lambda x: x["vibe_score"], reverse=True)
    
    print("리랭킹 완료. 가장 미학적으로 일치하는 매물이 상단에 배치되었습니다.")
    return reranked