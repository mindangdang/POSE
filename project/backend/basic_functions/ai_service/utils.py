import os
import uuid
import asyncio
from project.backend.app.manage.settings import load_backend_env
from supabase import create_client, Client
import os
import asyncio
import httpx
import psycopg 
from psycopg.rows import dict_row 
from google import genai
from google.genai import types
from pathlib import Path
from project.backend.app.schemas.response import TasteProfileResult 
from project.backend.app.manage.settings import IMAGE_DIR, load_backend_env
from project.backend.app.manage.resilience import with_llm_resilience

load_backend_env()
NEON_DB_URL = os.environ.get("NEON_DB_URL")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
BUCKET_NAME = "vibe-images"
LOCAL_IMAGE_DIR = Path(IMAGE_DIR)

if not url or not key:
    raise ValueError("Supabase 환경 변수가 설정되지 않았습니다.")

async def upload_generated_image(image_bytes: bytes) -> str:

    file_name = f"generated/{uuid.uuid4().hex}.jpg"

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

async def fetch_user_data_from_neon(user_id: str):
    try:
        async with await psycopg.AsyncConnection.connect(NEON_DB_URL) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT category, title, image_url,image_vector
                    FROM saved_posts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10;
                """
                await cur.execute(query, (user_id,))
                return await cur.fetchall()
    except Exception as e:
        print(f"DB 조회 실패: {e}")
        return []

async def get_image_bytes(url_or_filename: str) -> bytes | None:
    if not url_or_filename:
        return None

    # Case 1: 외부 URL (다운로드 실패해서 원본 URL만 남은 경우 등)
    if url_or_filename.startswith(('http://', 'https://')):
        try:
            async with httpx.AsyncClient(http2=True) as client:
                resp = await client.get(url_or_filename, timeout=5.0)
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            print(f"외부 이미지 로드 실패 ({url_or_filename}): {e}")
        return None
    
    # Case 2: 로컬 파일 (디스크 I/O를 논블로킹으로 처리)
    def read_local():
        try:
            candidate = Path(url_or_filename)
            if not candidate.is_absolute():
                candidate = LOCAL_IMAGE_DIR / candidate.name
            if candidate.exists() and candidate.is_file():
                return candidate.read_bytes()
        except Exception as e:
            print(f"로컬 이미지 로드 실패 ({url_or_filename}): {e}")
        return None

    return await asyncio.to_thread(read_local)

