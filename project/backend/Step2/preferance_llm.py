import os
import json
import asyncio
import psycopg 
from psycopg.rows import dict_row 
from pydantic import BaseModel, Field 
from google import genai
from google.genai import types
import httpx
from pathlib import Path
from urllib.parse import urljoin
from project.backend.config import IMAGE_DIR, load_backend_env

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
    http_options=types.HttpOptions(
        base_url=my_proxy_url
    )
)

LOCAL_IMAGE_DIR = IMAGE_DIR

# ==========================================
# 2. Pydantic 스키마 
# ==========================================
class TasteProfileResult(BaseModel):
    persona: str = Field(description="유저의 취향과 페르소나를 한 문장으로 정의하는 타이틀")
    unconscious_taste: str = Field(description="유저의 무의식적인 취향을 날카롭게 분석하는 텍스트 (2~3문장)")
    recommendation: str = Field(description="유저의 취향에 정합하는 새로운 키워드 제시 및 실존하는 장소/물건 추천")

# ==========================================
# 3. 시스템 프롬프트 (JSON 출력에 맞게 수정)
# ==========================================
SYSTEM_PROMPT = """
[System Persona]
주어진 데이터는 유저의 평소취향(current_profile)과 유저가 평소에 저장해둔 컨텐츠(사진+description)들이다. 당신은 유저의 평소취향과 저장해둔 컨텐츠들을 이용해 
표면적으로는 보이지 않는 취향 패턴을 파악하여 유저의 취향과 페르소나를 업데이트하는 human-data 분석가다. 당신의 목표는 단순 요약이 아니라 유저가 어떤 미학적 취향과 감각적 편향을 가진 사람인지 밝혀내는 것이다. 

[Core Analysis Rules]
-"카페를 좋아하고 옷에 관심이 많다" 식의 1차원적 요약 절대 금지
-형태학적 및 시각적 분석(Visual/Formal Analysis) : 조형 요소(선의 형태), Dominant Palette에서 보이는 색채 심리, 질감(Texture,촉각적 이미지)들을 분석할 것
-기호학적 분석 (Semiotic Analysis) : 롤랑 바르트의 기호학 이론을 기반으로 아이템이 사용자에게 어떤 **'의미'**로 읽히는지를 
 [외연(Denotation): 아이템의 객관적인 기능],[내포(Connotation): 아이템이 상징하는 가치],[신화(Myth): 해당 아이템들을 모음으로써 유저가 도달하고 싶어 하는 '이상적인 삶의 모습']의 관점에서 분석
-심리적 가치 및 동기 분석 (Psychological Motivation) : 다음의 요소들을 통해 수집 행위 뒤에 숨겨진 심리를 분석힌다. 
    1. 자기 대상화(Self-Objectification): "이 물건이 나를 대변한다"고 느끼는 지점.
    2. 수단적 vs 표현적 취향: 물건의 효율성을 중시하는지(수단적), 아니면 본인의 개성을 드러내는 디자인을 중시하는지(표현적) 구분.

[Thinking Process (내부 사고 과정)]
결과물을 작성하기 전, 반드시 다음 단계에 따라 데이터를 해석하라.
- Taste Patterns: 이미지에서 시각적/감각적 공통점 추출
- Identity Interpretation: 이 사람이 끌리는 공간과 사물들이 공유하는 ‘분위기’와 이 취향의 이면에 있는 페르소나를 추론.

[tone and manner]
- 철학적이거나 추상적인 표현은 피한다. 
- 두괄식 문장을 사용할 것.
- ('앤틱한', '섹시한', '고급진', '키치한', '날카로운') 과 같이 특유의 분위기나 느낌을 의미하는 단어들로 취향에 대해 설명할 것
- 제공된 데이터는 답변에 절대 언급하지 말 것.

[답변 형식(JSON)]
persona:"유저의 취향과 페르소나를 한 문장으로 정의하는 타이틀"
unconscious_taste:"유저의 무의식적인 취향을 날카롭게 분석하는 텍스트 (2~3문장)"
recommendation:"유저의 취향에 정합하는 새로운 키워드 제시 및 실존하는 장소/물건 추천"

"""

# ==========================================
# 4. 데이터 로드 및 포맷팅 함수 (비동기화)
# ==========================================

async def fetch_user_data_from_neon(user_id: int):
    try:
        # 비동기 DB 커넥션 및 dict_row 적용
        async with await psycopg.AsyncConnection.connect(NEON_DB_URL) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT facts, vibe_text, category, title, summary_text, image_url
                    FROM saved_posts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10;
                """
                await cur.execute(query, (str(user_id),))
                rows = await cur.fetchall()
                return rows
    except Exception as e:
        print(f"DB 조회 실패: {e}")
        return []

async def fetch_image_bytes(url: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                # Gemini SDK가 인식할 수 있는 형태(bytes 또는 types.Part)로 변환
                return resp.content
    except Exception as e:
        print(f"이미지 로드 실패 ({url}): {e}")
    return None

def fetch_local_image_bytes(filename_or_path: str):
    try:
        candidate = Path(filename_or_path)
        if not candidate.is_absolute():
            candidate = LOCAL_IMAGE_DIR / candidate.name

        if candidate.exists() and candidate.is_file():
            return candidate.read_bytes()
    except Exception as e:
        print(f"로컬 이미지 로드 실패 ({filename_or_path}): {e}")
    return None

def format_data_for_prompt(item: dict) -> str:

    facts = item.get("facts") or {}
    title = facts.get("title", "알 수 없음")
    location = facts.get("location_text", "위치 정보 없음")
    key_details = facts.get("key_details", [])

    post_text = f"""[Item {title}]
    - Category: {item.get('category', 'UNKNOWN')}
    - Location: {location}
    - Summary: {item.get('summary_text', '')}
    - Vibe: {item.get('vibe_text', '')}
    - Key Details: {key_details} """
    
    return post_text
    

# ==========================================
# 5. LLM 분석 실행 함수 (비동기화)
# ==========================================
async def analyze_vibe(user_id: int, current_profile: dict):
    raw_items = await fetch_user_data_from_neon(user_id)

    image_tasks = []
    for item in raw_items:
        url = item.get("image_url")
        if url:
            if url.startswith(('http://', 'https://')):
                image_tasks.append(fetch_image_bytes(url))
                continue

            local_image = fetch_local_image_bytes(url)
            if local_image:
                image_tasks.append(asyncio.sleep(0, result=local_image))
                continue
            image_tasks.append(asyncio.sleep(0, result=None))
        else:
            image_tasks.append(asyncio.sleep(0, result=None))

    # 2. 모든 이미지를 병렬로 다운로드 
    print(f"[User {user_id}] 이미지 데이터 병렬 로딩 중...")
    image_results = await asyncio.gather(*image_tasks)

    contents = []

    context = f"""
    [Current User Profile]
    - Persona: {current_profile.get('persona')}
    - Previous Analysis: {current_profile.get('unconscious_taste')}
    
    [New Activity]
    최근 유저가 다음 10개의 아이템을 새롭게 저장했다.평소 취향과 새로운 아이템들을 참고하여 취향의 '확장'이나 '변화'를 발견하고 업데이트된 취향을 생성하라.  
    기존 프로필과 상충되는 데이터가 있다면 취향의 '변화'로 해석하고, 일관된다면 취향의 '심화'로 해석하라.
    """
    contents.append(types.Part.from_text(text=context))
    
    for item, img_bytes in zip(raw_items, image_results):
        info = format_data_for_prompt(item)
        contents.append(types.Part.from_text(text=info))
        if img_bytes:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    try:
        print(f"[User {user_id}] 취향 프로필 분석 중 (Gemini Pro)...")
        # 무거운 LLM 처리는 스레드 풀에서 실행
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash', 
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4, 
                response_mime_type="application/json",
                response_schema=TasteProfileResult 
            ),
        )
        
        # Pydantic 객체로 파싱된 데이터
        data = response.parsed
        
        # 만약 response.parsed가 정상적인 Pydantic 객체가 아닐 경우 (문자열일 경우 등)
        if data is None:
            # fallback: response.text에서 직접 json 파싱 시도
            import json
            raw_text = response.text
            # 마크다운 태그 제거
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            data_dict = json.loads(clean_json)
            return data_dict # 딕셔너리 형태로 반환
            
        # 정상적인 Pydantic 객체인 경우 딕셔너리로 변환
        if hasattr(data, 'model_dump'):
            return data.model_dump()
        
        return data # 이미 dict인 경우
        
    except Exception as e:
        print(f"LLM 프로필 생성 중 오류 발생: {e}") 
        return None
