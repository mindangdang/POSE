import os
import uuid
import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel,Field
from project.backend.app.core.settings import load_backend_env
from fastapi import HTTPException
from supabase import create_client, Client
from project.backend.app.core.resilience import with_llm_resilience

load_backend_env()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
BUCKET_NAME = "vibe-images"

if not url or not key:
    raise ValueError("Supabase 환경 변수가 설정되지 않았습니다.")

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

class VibeGenerateRequest(BaseModel):
    prompt: str = Field(..., description="유저가 원하는 패션 아이템 (예: '연청 워시드 크롭 데님 자켓')")

@with_llm_resilience(fallback_default=HTTPException(status_code=500, detail="이미지 생성에 실패했습니다."))
async def generate_image_from_query(user_query: str) -> bytes:

    prompt = f"""
    [Image Generation Prompt Template]
    devide {user_query} into 4 key dimensions: category, details, color, mood. Then generate a detailed image generation prompt for a high-end contemporary designer brand's editorial product photography of the item described in user query.
    Strictly follow the structure and instructions below to create the prompt. Do not omit any dimension
    High-end contemporary designer brand's editorial product photography of (category).
    Design features: (details).
    Aesthetic: Archive fashion, avant-garde streetwear, minimalist and sophisticated silhouette, trendy mood.
    Color & Texture: (color) (If not specified, use muted, neutral, and monochromatic tones). Premium realistic material texture, highly detailed.
    Lighting & Camera: Shot on medium format camera, 85mm lens, studio softbox lighting, soft diffused shadows.
    Setting: Isolated on a clean off-white background, strictly no human, no mannequin, no floating elements. 8k resolution, ultra-photorealistic, minimalist e-commerce catalog style.
    """
    
    generate_response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="3:4")
        )
    )
    part = generate_response.candidates[0].content.parts[0]
    
    if getattr(part, 'inline_data', None) and part.inline_data.data:
        return part.inline_data.data
    elif getattr(part, 'image', None) and part.image.image_bytes:
        return part.image.image_bytes
    elif getattr(part, 'image_bytes', None):
        return part.image_bytes
        
    raise ValueError("생성된 이미지 데이터를 찾을 수 없습니다.")

async def upload_generated_image(image_bytes: bytes) -> str:

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

    print("Supabase로 이미지 업로드 중...")
    public_url = await asyncio.to_thread(_upload)
    
    print(f"업로드 완료! 퍼블릭 URL: {public_url}")
    return public_url
