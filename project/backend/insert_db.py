import os
import json
import psycopg2
from google import genai
from dotenv import load_dotenv

# 환경변수 세팅
load_dotenv()
neon_url = os.environ.get("NEON_DB_URL")
google_api_key = os.environ.get("GOOGLE_API_KEY")

# 구글 API 클라이언트 초기화 (임베딩용)
client = genai.Client(api_key=google_api_key)

# ==========================================
# 1. Vibe 텍스트 -> 벡터 변환 함수
# ==========================================
def get_vibe_vector(text: str):
    """감성 텍스트를 768차원 벡터로 변환합니다."""
    # 팩트 위주 게시물이라 감성 텍스트가 비어있다면 None 반환 (비용 절약)
    if not text or text.strip() == "":
        return None
    
    print(f"✨ 임베딩 변환 중... (텍스트: {text[:20]}...)")
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
        config={"task_type": "RETRIEVAL_DOCUMENT"} # DB 저장용 명시
    )
    # pgvector가 인식할 수 있도록 문자열 "[0.1, 0.2, ...]" 형태로 변환하여 반환
    return str(response.embeddings[0].values)

# ==========================================
# 2. JSON 데이터 DB Insert 함수
# ==========================================
def insert_items_to_db(user_id: str, source_url: str, extracted_items: list):
    """LLM이 추출한 아이템 리스트(JSON)를 DB에 저장합니다."""
    
    print(f"🔌 Neon DB 연결 중... ({len(extracted_items)}개 아이템 저장 대기)")
    conn = None
    
    try:
        conn = psycopg2.connect(neon_url)
        cursor = conn.cursor()

        # SQL Insert 쿼리 준비 (pgvector와 JSONB 타입에 맞춤)
        insert_query = """
            INSERT INTO saved_posts 
            (user_id, source_url, category, summary_text, vibe_text, vibe_vector, facts)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for item in extracted_items:
            category = item.get("category")
            summary_text = item.get("summary_text")
            vibe_text = item.get("vibe_text", "")
            
            # 파이썬 딕셔너리를 JSON 문자열로 변환 (PostgreSQL JSONB 컬럼용)
            facts_json = json.dumps(item.get("facts", {}), ensure_ascii=False)
            
            # 대망의 벡터 변환!
            vibe_vector = get_vibe_vector(vibe_text)

            # DB에 데이터 꽂아넣기
            cursor.execute(insert_query, (
                user_id, 
                source_url, 
                category, 
                summary_text, 
                vibe_text, 
                vibe_vector, 
                facts_json
            ))
            print(f"✅ DB 저장 완료: [{category}] {summary_text}")

        # 모든 저장이 정상적으로 끝났을 때만 확정(Commit)
        conn.commit()
        print("🎉 모든 데이터가 성공적으로 적재되었습니다!")
        
    except Exception as e:
        print(f"❌ DB 저장 중 에러 발생: {e}")
        if conn:
            conn.rollback() # 중간에 에러 나면 저장된 것들 롤백 (안전 장치)
    finally:
        if conn:
            cursor.close()
            conn.close()