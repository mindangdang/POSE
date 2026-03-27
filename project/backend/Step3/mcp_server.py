import os
import json
import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from fastmcp import FastMCP
from google import genai
from google.genai import types
from dotenv import load_dotenv
from Step2.insert_DB import get_vibe_vectors_batch

# 1. 초기화
mcp = FastMCP("VibeSearch_Agents")
NEON_DB_URL = os.environ.get("NEON_DB_URL")
load_dotenv()
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

# ===================================================================
# Helper Function (DB Fetch)
# ===================================================================
def fetch_similar_items_from_neon(user_id: int, query_vector: list[float], limit: int = 5) -> str:
    """pgvector를 사용하여 쿼리 벡터와 가장 유사한 취향 데이터를 가져옵니다."""
    if not query_vector:
        return ""
        
    try:
        conn = psycopg.connect(NEON_DB_URL)
        register_vector(conn) 
        cur = conn.cursor(cursor_factory=dict_row)
        
        # 코사인 거리 연산자(<=>)로 의미론적 유사도가 높은 상위 N개 추출
        query = """
            SELECT extracted_data 
            FROM saved_posts 
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
# Tool 1: Query Expansion MCP
# ===================================================================
@mcp.tool()
async def expand_search_queries(current_taste_profile: str, user_query: str, user_id: int) -> list[str]:
    query_vector = get_vibe_vectors_batch(list(user_query))
    similiar_items = fetch_similar_items_from_neon(user_id = user_id, query_vector = query_vector) 
    vibe_context = current_taste_profile

    """
    원본 쿼리와 취향 맥락(Vibe Context)을 결합하여 구글 검색에서 고감도 큐레이팅 정보만을 찾아내는데 최적화된 검색 쿼리(Dorks)를 생성합니다.
    """
    prompt = f"""
    당신은 검색 엔진의 노이즈(SEO 최적화된 광고, 무미건조한 핫플 정보)를 혐오하는 검색 설계자다.
    
    [User's Raw Query]: "{user_query}"
    [User's Vibe Context]: "{vibe_context,similiar_items}"
    
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
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return [f"Error generating queries: {str(e)}"]

if __name__ == "__main__":
    print(" Vibe Search Vector MCP Server is running...")
    mcp.run()