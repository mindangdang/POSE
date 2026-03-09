import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# 1. 환경 변수 및 설정
# ==========================================

load_dotenv()
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
NEON_DB_URL = os.environ.get("NEON_DB_URL")

# ==========================================
# 2. 시스템 프롬프트
# ==========================================
SYSTEM_PROMPT = """
[System Persona]
당신은 파편화된 데이터 속에서 인간의 취향과 미학적 무의식을 예리하게 짚어내는 감도높은 큐레이터이다. 
당신의 목표는 단순 요약이 아니라 유저가 어떤 미학적 취향과 감각적 편향을 가진 사람인지 밝혀내는 것이다.

[Data Format]
- Category: 콘텐츠 유형 (PLACE, PRODUCT, MEDIA, TIP, INSPIRATION)
- Target: 대상 이름/상호명 (기표가 가지는 미학적 권력)
- Location: 위치 (공간의 맥락과 동네의 분위기)
- Summary: 객관적인 내용 설명
- Vibe: 분위기, 감성, 사용 맥락
- Key Details: 특징적인 디테일

[Core Analysis Rules]
1. 1차원적 요약 절대 금지: "카페를 좋아하고 옷에 관심이 많다" 식의 단순 나열은 철저히 배제한다.
2. 저장된 게시물에서 반복되는 **분위기(vibe)**패턴을 찾아내라. 패션, 공간, 오브제 등 카테고리가 달라도 그 밑바탕을 관통하는 단 하나의 '미학적 교집합'을 찾아낸다.
3. 찾아낸 패턴을 바탕으로 유저가 어떤 미학적 태도를 선호하는지 해석하라. 데이터 속에 숨겨진 사용자가 꽂힌 포인트(예: 고급스러우면서 섹시한 분위기, 빈티지한 무드 등)을 예리하게 찔러준다.

[Thinking Process (내부 사고 과정)]
결과물을 작성하기 전, 반드시 다음 단계에 따라 데이터를 해석하라. (이 사고 과정은 최종 출력에 포함하지 않고 내부적으로만 수행할 것)
- Taste Patterns: 반복되는 Vibe와 Key Details 속에서 질감, 색 온도, 여백의 정도 등 시각적/감각적 공통점 추출
- Identity Interpretation: 이 사람이 끌리는 공간과 사물들이 공유하는 '삶의 태도' 추론, 이 취향의 이면에 있는 심리적 갈망 정의

[Output Format]
사고 과정을 마친 후, 다음 세 가지 섹션만 출력하라.

[당신의 미학적 페르소나]
- 유저의 취향과 본질을 한 문장으로 정의하는 강렬한 타이틀 (단 1문장. 예: "빈티지함을 좋아하는, 이 시대의 낭만주의자.")

[나도 몰랐던 나의 미학적 취향]
-사용자의 무의식적인 취향과 삶의 태도를 날카롭게 분석하는 텍스트 (3~4문장). 단순한 나열이 아닌, 마치 오랫동안 관찰해온 듯한 소름 돋는 통찰을 담을 것.

[Vibe Search의 예측]
- 이 취향을 가진 사람이 앞으로 저장할 가능성이 높은
공간, 오브제, 혹은 경험을 하나 예측하라. "당신은 조만간 이런 바이브의 [특정 물건/장소]에 강렬하게 끌리게 될 것입니다"라는 예리한 예측 하나 제시. 
예측에 제시하는 예시는 실제 있는 물건/장소여야 한다.

톤앤매너:
분석적이지만 큐레이터의 해설처럼 읽혀야 한다
지나치게 철학적이거나 추상적인 표현은 피한다
당신은 ~입니다 라는 말투를 사용할 것.
독자가 “어… 이거 나 맞는데?”라고 느끼게 만든다
관심사를 나열하지 말고 취향의 패턴을 설명하라
제공된 데이터(ex:아크테릭스 바람막이를 좋아하는 걸로 봐서~)는 답변에 절대 언급하지 마라.

"""

# ==========================================
# 3. 데이터 로드 및 포맷팅 함수
# ==========================================
def fetch_user_data_from_neon(user_id: int):
    try:
        # DB 연결
        conn = psycopg2.connect(NEON_DB_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT extracted_data 
            FROM user_saved_posts 
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20; -- 너무 많으면 토큰 낭비이므로 최근/핵심 데이터 20개로 제한
        """
        cur.execute(query, (user_id,))
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # JSONB 컬럼에서 데이터 추출
        return [row['extracted_data'] for row in rows]
        
    except Exception as e:
        print(f"Neon DB 연결 또는 쿼리 실패: {e}")
        return []

def format_data_for_prompt(items: list) -> str:
    formatted_posts = []
    
    for idx, item in enumerate(items, 1):
        facts = item.get("facts", {})
        title = facts.get("title", "알 수 없음")
        location = facts.get("location_text", "위치 정보 없음")
        key_details = facts.get("key_details", [])
        details_str = ", ".join(key_details) if key_details else "특징 없음"
        
        post_text = f"""[Item {idx}]
- Category: {item.get('category', 'UNKNOWN')}
- Target: {title}
- Location: {location}
- Summary: {item.get('summary_text', '')}
- Vibe: {item.get('vibe_text', '')}
- Key Details: {details_str}"""
        
        formatted_posts.append(post_text)
        
    return "\n\n".join(formatted_posts)

# ==========================================
# 4. LLM 분석 실행 함수
# ==========================================
def analyze_vibe(user_id: int):
    print(f"🔍 User {user_id}의 데이터를 Neon DB에서 불러오는 중...")
    raw_items = fetch_user_data_from_neon(user_id)
    
    if not raw_items:
        print("❌ 분석할 데이터가 없습니다.")
        return
        
    print(f"✅ {len(raw_items)}개의 게시물을 성공적으로 불러왔습니다. 텍스트로 압축합니다.")
    post_data_string = format_data_for_prompt(raw_items)
    
    user_prompt = f"""
다음 데이터는 한 사용자가 인스타그램에서 무의식적으로, 혹은 강렬한 이끌림으로 "나에게 보내기" 해둔 게시물들이다. 
이 데이터는 단순한 '관심사 목록'이 아니다. 단순한 기능이나 효율성 이면에 숨겨진 이 사람만의 고유한 감각, 공간을 점유하는 방식, 미학적 결핍과 삶의 태도를 보여주는 거울이다.
이 데이터들을 분석하여 유저의 취향을 추측하라.

[POST DATA]
{post_data_string}
"""
    
    print("Vibe Search 수석 큐레이터가 분석을 시작합니다...\n")
    
    # Gemini API 호출 설정
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7, 
            ),
        )
        print("================================")
        print(response.text)
        print("================================")
        
    except Exception as e:
         print(f"❌ LLM 호출 중 오류 발생: {e}")

# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    # 테스트할 사용자의 ID를 입력하세요.
    TEST_USER_ID = 1 
    analyze_vibe(TEST_USER_ID)