import os
import json
import psycopg2
from pgvector.psycopg2 import register_vector  
from google import genai
from dotenv import load_dotenv
from google.genai import types

# 환경변수 세팅
load_dotenv()
neon_url = os.environ.get("NEON_DB_URL") 
google_api_key = os.environ.get("GOOGLE_API_KEY")

# 구글 API 클라이언트 초기화
client = genai.Client(api_key=google_api_key)

# 💡 최신 임베딩 모델로 변경 (차원 축소 완벽 지원)
MODEL_NAME = "text-embedding-001" 

# ==========================================
# 1. Vibe 텍스트 -> 벡터 변환 함수
# ==========================================
def get_vibe_vector(text: str):
    if not text or text.strip() == "":
        return None

    try:
        response = client.models.embed_content(
            model=MODEL_NAME,
            contents=text, # 리스트가 아닌 단일 텍스트 문자열 그대로 전달
            config=types.EmbedContentConfig(
                output_dimensionality=768  # gemini-embedding-001도 768차원 축소 완벽 지원
            )
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"⚠️ 임베딩 생성 실패: {e}")
        return None

# ==========================================
# 2. JSON 데이터 DB Insert 함수
# ==========================================
def insert_items_to_db(user_id: str, source_url: str, extracted_items: list):
    conn = None
    cursor = None # 💡 finally 블록에서의 참조 에러를 막기 위해 초기화
    
    try:
        conn = psycopg2.connect(neon_url)
        register_vector(conn)  # 💡 핵심: psycopg2가 파이썬 리스트를 vector 컬럼에 넣을 수 있게 허가함
        cursor = conn.cursor()

        # 💡 ON CONFLICT 추가: 중복된 URL+Category 데이터가 들어오면 무시하고 다음 것 저장
        insert_query = """
            INSERT INTO saved_posts 
            (user_id, source_url, category, summary_text, vibe_text, vibe_vector, facts)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_url, category) DO NOTHING; 
        """

        for item in extracted_items:
            category = item.get("category")
            summary_text = item.get("summary_text")
            vibe_text = item.get("vibe_text", "")
            
            # JSON 변환
            facts_json = json.dumps(item.get("facts", {}), ensure_ascii=False)
            
            # 벡터 변환
            vibe_vector = get_vibe_vector(vibe_text)

            # DB 실행
            cursor.execute(insert_query, (
                user_id, 
                source_url, 
                category, 
                summary_text, 
                vibe_text, 
                vibe_vector, 
                facts_json
            ))

        conn.commit()
        print(f"✅ DB 저장 완료: {len(extracted_items)}개의 타겟")
        
    except Exception as e:
        print(f"❌ DB 저장 중 에러 발생: {e}")
        if conn:
            conn.rollback() 
    finally:
        # 안전한 자원 해제
        if cursor:
            cursor.close()
        if conn:
            conn.close()