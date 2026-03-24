import os
import json
import asyncio
import psycopg # 
from psycopg.rows import dict_row #
from pydantic import BaseModel, Field # 
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# 1. 환경 변수 및 설정
# ==========================================
load_dotenv()
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

# ==========================================
# 2. Pydantic 스키마 (프론트엔드 UI 파괴 방지용)
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
주어진 데이터는 유저가 자신의 취향이거나 유용하다고 생각하여 저장해둔 컨텐츠들이다. 당신은 데이터들의 표면에서는 드러나지 않는 공통적인 패턴과 경향을 파악하여 유저의 취향과 페르소나를 추론해내는 human-data 분석가다. 
당신의 목표는 단순 요약이 아니라 유저가 어떤 미학적 취향과 감각적 편향을 가진 사람인지 밝혀내는 것이다.

[Core Analysis Rules]
1. "카페를 좋아하고 옷에 관심이 많다" 식의 1차원적 요약 절대 금지
2. 데이터에서 공통적으로 보이는 **분위기(vibe)** 패턴을 찾아내라. 패션, 공간, 오브제 등 카테고리가 달라도 그 밑바탕을 관통하는 단 하나의 '미학적 교집합'을 찾아낸다.
3. 찾아낸 패턴을 바탕으로 유저가 어떤 분위기, 느낌을 선호하는지 해석하라. 유저가 꽂힌 포인트(예: 고급스러우면서 섹시한 분위기 등)를 예리하게 찔러준다.

[Thinking Process (내부 사고 과정)]
결과물을 작성하기 전, 반드시 다음 단계에 따라 데이터를 해석하라.
- Taste Patterns: Vibe와 Key Details 속에서 시각적/감각적 공통점 추출
- Identity Interpretation: 이 사람이 끌리는 공간과 사물들이 공유하는 ‘분위기’와 이 취향의 이면에 있는 페르소나를 추론.

[tone and manner]
- 철학적이거나 추상적인 표현은 피한다. 
- 두괄식 문장을 사용할 것.
- ('앤틱한', '섹시한', '고급진', '키치한', '날카로운') 과 같이 특유의 분위기나 느낌을 의미하는 단어들로 취향에 대해 설명할 것
- 제공된 데이터는 답변에 절대 언급하지 말 것.
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
                    SELECT facts, reviews, vibe_text, category, title, summary_text
                    FROM saved_posts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 20;
                """
                await cur.execute(query, (str(user_id),))
                rows = await cur.fetchall()
                return rows
    except Exception as e:
        print(f"DB 조회 실패: {e}")
        return []

def format_data_for_prompt(items: list) -> str:
    formatted_posts = []
    
    for idx, item in enumerate(items, 1):
        facts = item.get("facts") or {}
        title = facts.get("title", "알 수 없음")
        location = facts.get("location_text", "위치 정보 없음")
        key_details = facts.get("key_details", [])
        
        # key_details가 리스트가 아니라 문자열일 경우를 대비한 방어 코드
        if isinstance(key_details, list):
            details_str = ", ".join(key_details) if key_details else "특징 없음"
        else:
            details_str = str(key_details)
            
        reviews = item.get("reviews") or {}
        star_review = reviews.get("star_review", "")
        core_summary = reviews.get("core_summary", "")

        post_text = f"""[Item {idx}]
        - Category: {item.get('category', 'UNKNOWN')}
        - Target: {title}
        - Location: {location}
        - Summary: {item.get('summary_text', '')}
        - Vibe: {item.get('vibe_text', '')}
        - Key Details: {details_str}
        - Review: {star_review} - {core_summary}"""
        
        formatted_posts.append(post_text)
        
    return "\n\n".join(formatted_posts)

# ==========================================
# 5. LLM 분석 실행 함수 (비동기화)
# ==========================================
async def analyze_vibe(user_id: int):
    raw_items = await fetch_user_data_from_neon(user_id)

    if not raw_items:
        return "취향 데이터를 생성할 수 없습니다. 피드에 아이템을 추가해 주세요."
        
    post_data_string = format_data_for_prompt(raw_items)
    
    user_prompt = f"""
다음 데이터는 한 유저가 저장해둔 컨텐츠들이다. 
이 데이터들을 분석하여 유저의 취향을 추측하라.

[POST DATA]
{post_data_string}
"""    
    try:
        print(f"[User {user_id}] 취향 프로필 분석 중 (Gemini Pro)...")
        # 무거운 LLM 처리는 스레드 풀에서 실행
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.5-pro', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.6, 
                response_mime_type="application/json",
                response_schema=TasteProfileResult, #구조화된 출력 강제
            ),
        )
        
        # Pydantic 객체로 파싱된 데이터
        data = response.parsed
        
        # DB의 summary(TEXT) 컬럼 구조에 맞게 예쁘게 마크다운 텍스트로 조립
        final_summary = f"**페르소나**\n{data.persona}\n\n**나도 몰랐던 나의 취향**\n{data.unconscious_taste}\n\n**추천**\n{data.recommendation}"
        
        return final_summary
        
    except Exception as e:
        print(f"LLM 프로필 생성 중 오류 발생: {e}") 
        return None