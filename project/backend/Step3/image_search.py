import os
import uuid
import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel,Field
from project.backend.app.core.settings import load_backend_env
from fastapi import APIRouter, HTTPException

GENERATION_MODEL = "imagen-3.0-generate-002"

class VibeGenerateRequest(BaseModel):
    prompt: str = Field(..., description="유저가 원하는 패션 아이템 (예: '연청 워시드 크롭 데님 자켓')")

class LensSearchResult(BaseModel):
    title: str
    link: str
    source: str
    thumbnail: str
    price: str = "가격 미상" 

class VibeSearchResponse(BaseModel):
    success: bool
    generated_vibe_image_url: str 
    recommended_items: list[LensSearchResult]

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
async def generate_image_from_query(user_query: str) -> bytes:

    prompt = f"""
    High-end fashion editorial photography, a single clothing item: {user_query}.  
    Clean white studio background, photorealistic, 8k resolution, highly detailed texture and fabric.
    """
    
    try:
        generate_response = await client.aio.models.generate_image(
            model=GENERATION_MODEL,
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                aspect_ratio="3:4", # 룩북 감성
                add_watermark=False, # 워터마크 제거 (렌즈 검색 정확도 상승)
                include_rai_reasoning=True, # 안전성 검사 결과 포함
                output_mime_type="image/jpeg"
            )
        )
        generated_image = generate_response.generated_images[0]

        return generated_image

    except Exception as e:
        print(f"이미지 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="이미지 생성에 실패했습니다.")



