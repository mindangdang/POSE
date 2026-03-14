import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from fastmcp import FastMCP
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. 초기화
mcp = FastMCP("VibeSearch_Agents")
NEON_DB_URL = os.environ.get("DATABASE_URL")
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("⚠️ .env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=api_key)

# ===================================================================
# Helper Function (DB Fetch)
# ===================================================================
def fetch_similar_items_from_neon(user_id: int, query_vector: list[float], limit: int = 5) -> str:
    """pgvector를 사용하여 쿼리 벡터와 가장 유사한 취향 데이터를 가져옵니다."""
    if not query_vector:
        return ""
        
    try:
        conn = psycopg2.connect(NEON_DB_URL)
        register_vector(conn) # psycopg2에 pgvector 타입 등록
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 코사인 거리 연산자(<=>)로 의미론적 유사도가 높은 상위 N개 추출
        query = """
            SELECT extracted_data 
            FROM user_saved_posts 
            WHERE user_id = %s
            ORDER BY text_embedding <=> %s::vector
            LIMIT %s;
        """
        cur.execute(query, (user_id, query_vector, limit))
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        formatted_posts = []
        for idx, row in enumerate(rows, 1):
            item = row['extracted_data']
            facts = item.get("facts", {})
            post_text = f"[Item {idx}] Category: {item.get('category')} | Target: {facts.get('title')} | Vibe: {item.get('vibe_text')} | Details: {', '.join(facts.get('key_details', []))}"
            formatted_posts.append(post_text)
            
        return "\n".join(formatted_posts)
    except Exception as e:
        print(f"Neon DB Vector Search Error: {e}")
        return ""

# ===================================================================
# Tool 1: 취향 맥락 수집기 (Taste Context MCP)
# ===================================================================
@mcp.tool()
def get_taste_context(user_query: str, query_vector: list[float], user_id: int) -> str:
    """
    미리 변환된 쿼리 벡터를 주입받아, DB에서 가장 유사한 취향 데이터를 찾고 LLM이 맥락을 분석합니다.
    
    Args:
        user_query: 사용자의 원본 텍스트 질문 (예: "도쿄 조용한 카페 추천해줘")
        query_vector: 메인 에이전트 측에서 생성하여 넘겨주는 쿼리의 임베딩 벡터 배열
        user_id: 사용자 식별자
    """
    # 1. 메인 에이전트가 넘겨준 query_vector로 바로 DB 찌르기
    db_context_string = fetch_similar_items_from_neon(user_id, query_vector, limit=5)
    
    if not db_context_string:
        return "사용자의 취향 데이터를 불러오지 못했거나 일치하는 맥락이 없습니다."

    # 2. LLM에게 선별된 데이터를 주고 '바이브' 요약 지시
    prompt = f"""
    당신은 사용자의 현재 질문을 분석하여, 취향 DB에서 가장 훌륭한 레퍼런스를 골라내는 '맥락 수집가'이다.
    
    [사용자 질문]: "{user_query}"
    [pgvector가 찾아낸 가장 유사한 과거 취향 데이터 Top 5]: 
    {db_context_string}
    
    [Instruction]
    제공된 데이터들은 사용자의 질문과 의미적으로 유사한 과거의 시각적/맥락적 기록들이다. 
    이 데이터들의 공통적인 '미학적 편향'을 바탕으로, 이 사용자가 현재 찾고 있을 공간/물건의 무드를 3~4문장으로 요약하라.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error extracting vibe context: {str(e)}"

# ===================================================================
# Tool 2: 큐레이팅 쿼리 확장기 (Query Expansion MCP)
# ===================================================================
@mcp.tool()
def expand_search_queries(user_query: str, vibe_context: str) -> list[str]:
    """
    원본 쿼리와 취향 맥락(Vibe Context)을 결합하여 구글 검색에서 고감도 큐레이팅 정보만을 찾아내는데 최적화된 검색 쿼리(Dorks)를 생성합니다.
    """
    prompt = f"""
    당신은 검색 엔진의 노이즈(SEO 최적화된 광고, 무미건조한 핫플 정보)를 혐오하는 검색 설계자다.
    
    [User's Raw Query]: "{user_query}"
    [User's Vibe Context]: "{vibe_context}"
    
    [Instruction]
    구글/네이버에서 감도 높은 디깅 결과만 나오도록 검색 쿼리를 고도화하라.
    1. 마이너스 연산자 필수 사용: -협찬 -원고료 -핫플 -인스타감성 -광고
    2. Vibe Context에 맞는 디테일 키워드(물성, 무드, 브랜드 등) 주입
    3. 필요시 감도 높은 출처(site:fruitsfamily.com 등) 제한 활용
    
    [Output Format]
    반드시 파이썬의 리스트(List) 형태의 JSON 배열만 출력하라. 다른 텍스트는 절대 금지.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return [f"Error generating queries: {str(e)}"]

if __name__ == "__main__":
    print("🚀 Vibe Search Vector MCP Server is running...")
    mcp.run()