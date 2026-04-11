import os
import uuid
import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel,Field
from project.backend.app.core.settings import load_backend_env
from fastapi import HTTPException
from supabase import create_client, Client

GENERATION_MODEL = "imagen-3.0-generate-002"
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase 환경 변수가 설정되지 않았습니다.")

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

supabase: Client = create_client(url, key)
BUCKET_NAME = "vibe-images"

async def upload_generated_image(image_bytes: bytes) -> str:
    """
    생성된 이미지를 Supabase Storage에 업로드하고 퍼블릭 URL을 반환합니다.
    """
    file_name = f"generated/{uuid.uuid4().hex}.jpg"

    # Supabase SDK는 동기식 방식이 섞여 있으므로 안전하게 스레드에서 실행
    def _upload():
        try:
            # 1. 스토리지에 파일 업로드 (Content-Type 지정으로 브라우저에서 바로 보이게 함)
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_name,
                file=image_bytes,
                file_options={"content-type": "image/jpeg"}
            )
            
            # 2. 방금 올린 파일의 퍼블릭 URL 가져오기
            return supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)
            
        except Exception as e:
            print(f"Supabase 업로드 에러: {e}")
            raise Exception("클라우드 이미지 저장에 실패했습니다.")

    print("☁️ Supabase로 이미지 업로드 중...")
    public_url = await asyncio.to_thread(_upload)
    
    print(f"✅ 업로드 완료! 퍼블릭 URL: {public_url}")
    return public_url
