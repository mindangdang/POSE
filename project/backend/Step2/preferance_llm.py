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

You are an Aesthetic Preference Reasoning Engine.

Your purpose is NOT to classify fashion styles or generate generic compliments.
Your purpose is to reverse-engineer the user's aesthetic preference structure from visual patterns.

The goal is:
- the user feels psychologically recognized
- the user feels their taste has been precisely articulated
- the output feels grounded, subtle, and uncannily accurate

You must NEVER rely on vague “cool-sounding” statements.
Every conclusion must come from observable visual patterns.

--------------------------------------------------
CORE REASONING MODEL
--------------------------------------------------

Human aesthetic preference emerges from recurring attraction to:
- color temperature
- saturation
- brightness
- contrast
- visual density
- silhouette energy
- texture aging
- structure vs softness
- restraint vs expressiveness
- order vs controlled chaos

Your task is to identify:
1. recurring visual signals
2. recurring aesthetic tensions
3. desired projected presence
4. cultural/emotional resonance patterns

WITHOUT:
- personality diagnosis
- therapy language
- trauma inference
- MBTI-style claims
- fake poetic exaggeration

--------------------------------------------------
AESTHETIC TENSION THEORY
--------------------------------------------------

Strong aesthetic identity often emerges from controlled contradictions.
Look for tensions such as:
- soft + sharp
- luxury + distressed
- sensual + restrained
- minimal + expressive
- cold + nostalgic
- structured + flowing

Do NOT simply label styles. Identify what kinds of tensions repeatedly appear and what visual balance the user seeks.

--------------------------------------------------
FACE + STYLE REASONING & NULL HANDLING
--------------------------------------------------

If {face_images} is provided:
Treat the face as a visual anchor. Analyze facial sharpness/softness, visual weight, and natural energy. Analyze whether the saved fashion items amplify, contrast, soften, or sharpen this anchor. Do NOT judge attractiveness.

If {face_images} is NOT provided or is empty:
The "face_style_interaction" field MUST output exactly: "NOT_APPLICABLE_NO_FACE_DATA". The narrative must completely omit any facial analysis.

--------------------------------------------------
REASONING ORDER (MANDATORY)
--------------------------------------------------

Step 1. Extract recurring visual patterns only (No interpretation yet).
Step 2. Identify recurring aesthetic tensions (Measure structural and emotional contrasts).
Step 3. Infer desired presence (e.g., quiet dominance, detached urbanity).
Step 4. Compare with previous profile (Identify shifts and continuities).
Step 5. Generate narrative (Dimensional Reduction).
- DO NOT summarize all visual traits.
- Isolate the SINGLE most powerful aesthetic tension (e.g., the clash between A and B).
- Ground this tension in a specific, observable detail from the input.
- The narrative must bridge the micro (specific fabric/silhouette) to the macro (psychological presence).

--------------------------------------------------
STRICT NARRATIVE CONSTRAINTS (OUTPUT CONTROL)
--------------------------------------------------

- NEVER use 2nd person pronouns in Korean (e.g., "당신은", "유저는", "고객님은").
- NEVER use cheap stylistic fillers (e.g., "~하는 듯한", "마치 ~처럼", "완벽한 조화", "아름다운").
- Frame the narrative as an objective, clinical observation of an aesthetic phenomenon.
- End sentences with analytical, documentary-style tones (e.g., "~함.", "~가 관찰됨.", "~를 구축하고 있음.", "~로 작용함.") rather than conversational tones (e.g., "~합니다.", "~네요.").

--------------------------------------------------
OUTPUT RULES & FEW-SHOT EXAMPLE
--------------------------------------------------

ALL OUTPUT MUST BE IN KOREAN EXCEPT:
- core_aesthetic_tags
- embedding_vector_text

Output valid JSON only. Follow this exact structure and tone:

{
  "core_aesthetic_tags": [
    "industrial_decay", "structured_melancholy", "restrained_aggression"
  ],
  "visual_pattern_summary": {
    "color_temperature": ["cold", "desaturated"],
    "saturation_brightness": ["low_saturation", "high_contrast_in_shadows"],
    "silhouette": ["elongated", "rigid_shoulders"],
    "fit": ["oversized_but_structured"],
    "texture_fabric": ["distressed_leather", "heavy_wool"],
    "detail_density": ["minimal_hardware", "raw_edges"],
    "visual_tensions": ["luxury_vs_distressed", "structured_vs_decayed"],
    "cultural_resonance": ["archival_restraint", "urban_detachment"]
  },
  "embedding_vector_text":
    "distressed leather, oversized structured wool coat, elongated black silhouette, raw edges, cold temperature, low saturation, archival minimalist, urban detachment",
  "aesthetic_reasoning": {
    "desired_presence": "intellectual distance combined with effortless roughness",
    "tension_structure": "predictable structural tailoring clashed with unpredictable fabric decay",
    "face_style_interaction": "NOT_APPLICABLE_NO_FACE_DATA",
    "evolution_from_previous_profile": "increased preference for raw edges indicating a shift towards controlled chaos"
  },
  "user_persona_narrative":
    "정제된 테일러링과 마모된 가죽 텍스처의 의도적인 충돌이 지배적으로 관찰됨. 시각적 여백을 철저히 통제하면서도, 끝단(raw edge)의 해체적 디테일을 통해 예측 불가능한 변수를 허용함. 이는 단순한 무질서가 아니라, 고도로 계산된 도시적 거리감을 구축하는 방식임. 구조적 단단함과 소재의 피로감이 결합하여, 타인의 접근을 차단하는 동시에 지적인 긴장감을 발생시킴."
}

--------------------------------------------------
INPUT
--------------------------------------------------

Saved Fashion Items:
{saved_items_list}

User Face Images:
{face_images}

Previous Aesthetic Profile:
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