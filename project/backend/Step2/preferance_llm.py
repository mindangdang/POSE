import os
import asyncio
import httpx
import psycopg 
from psycopg.rows import dict_row 
from pydantic import BaseModel, Field 
from google import genai
from google.genai import types
from pathlib import Path

from project.backend.app.core.settings import IMAGE_DIR, load_backend_env
from project.backend.app.core.resilience import with_llm_resilience

# ==========================================
# 1. 환경 변수 및 설정
# ==========================================
load_backend_env()
NEON_DB_URL = os.environ.get("NEON_DB_URL")
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(base_url=my_proxy_url)
)

LOCAL_IMAGE_DIR = Path(IMAGE_DIR)

# ==========================================
# 2. Pydantic 스키마 
# ==========================================
class TasteProfileResult(BaseModel):
    persona: str = Field(description="유저의 취향과 페르소나를 한 문장으로 정의하는 타이틀")
    unconscious_taste: str = Field(description="유저의 무의식적인 취향을 분석하는 텍스트 (2~3문장)")
    recommendation: str = Field(description="유저의 취향에 정합하는 새로운 키워드 제시 및 실존하는 장소/물건 추천")

# ==========================================
# 3. 시스템 프롬프트 (토큰 다이어트 적용)
# ==========================================
SYSTEM_PROMPT = """
[System]

You are an elite fashion aesthetic profiling engine.

Your task:
1. Extract recurring visual patterns from saved fashion items
2. Generate embedding-friendly fashion descriptors
3. Infer aesthetic tendencies and desired presence grounded ONLY in visible style signals
4. Compare continuity/evolution from previous profile

Do NOT:
- diagnose personality
- infer trauma/politics/lifestyle/intelligence
- generate generic compliments
- rely on shallow labels (old money, clean girl, etc.)

Focus on:
- silhouette
- fit
- proportion
- texture
- fabric treatment
- color temperature
- layering
- detail density
- visual tension
- atmosphere

Detect subtle contradictions when relevant:
- soft + sharp
- luxury + distressed
- sensual + restrained
- minimal + aggressive
- vintage + futuristic

Use dense morphology-rich fashion language optimized for CLIP/text embedding retrieval.

Narrative rules:
- emotionally perceptive but visually grounded
- subtle and culturally literate
- no cringe poetry
- no overclaiming
- every interpretation must map to observable patterns

ALL OUTPUT MUST BE IN KOREAN EXCEPT:
- embedding_vector_text
- core_aesthetic_tags

[Output JSON Schema]

{
  "core_aesthetic_tags": [
    "3~7 English aesthetic keywords"
  ],

  "visual_pattern_summary": {
    "silhouette": [],
    "fit": [],
    "texture": [],
    "color_palette": [],
    "detail_structure": [],
    "atmospheric_mood": [],
    "style_tensions": []
  },

  "embedding_vector_text":
    "Dense English retrieval-oriented visual descriptors separated by commas",

  "aesthetic_interpretation": {
    "desired_presence": "",
    "visual_tension": "",
    "evolution_from_previous_profile": ""
  },

  "user_persona_narrative":
    "3~5 sentence refined Korean narrative grounded in visible aesthetic patterns"
}

[Input]

Saved Items:
{saved_items_list}

Previous Profile:
{current_profile}
"""

# ==========================================
# 4. 데이터 로드 및 포맷팅 (비동기화 및 통합)
# ==========================================
async def fetch_user_data_from_neon(user_id: str):
    try:
        async with await psycopg.AsyncConnection.connect(NEON_DB_URL) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT facts, recommend, category, sub_category, title, image_url,image_vector
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

def format_data_for_prompt(item: dict) -> str:
    facts = item.get("facts") or {}
    title = facts.get("title", "알 수 없음")
    location = facts.get("location_text", "위치 정보 없음")
    key_details = facts.get("key_details", [])

    return f"""[Item {title}]
    - Category: {item.get('category', 'UNKNOWN')}
    - Location: {location}
    - Recommend: {item.get('recommend', '')}
    - Key Details: {key_details} """

# ==========================================
# 5. LLM 분석 실행 함수
# ==========================================
@with_llm_resilience(fallback_default=None)
async def analyze_vibe(user_id: str, current_profile: dict):
    raw_items = await fetch_user_data_from_neon(user_id)
    if not raw_items:
        return None

    print(f"[User {user_id}] 이미지 데이터 병렬 로딩 중...")
    image_tasks = [get_image_bytes(item.get("image_url")) for item in raw_items]
    image_results = await asyncio.gather(*image_tasks)

    contents = []
    context = f"""
    [Current User Profile]
    - Persona: {current_profile.get('persona', '분석 전')}
    - Previous Analysis: {current_profile.get('unconscious_taste', '데이터 없음')}
    
    [New Activity]
    최근 유저가 다음 아이템들을 새롭게 저장했다. 기존 프로필과 새로운 데이터를 비교하여 취향의 '확장', '변화', 또는 '심화'를 발견하고 업데이트된 프로필을 생성하라.
    """
    contents.append(types.Part.from_text(text=context))
    
    for item, img_bytes in zip(raw_items, image_results):
        info = format_data_for_prompt(item)
        contents.append(types.Part.from_text(text=info))
        if img_bytes:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    print(f"[User {user_id}] 취향 프로필 분석 중 (Gemini 2.5 Flash)...")
    response = await client.aio.models.generate_content(
        model='gemini-2.5-flash', 
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4, 
            response_mime_type="application/json",
            response_schema=TasteProfileResult # 
        ),
    )

    return response.parsed.model_dump()