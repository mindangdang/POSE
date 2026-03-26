import os
import json
import asyncio
import psycopg 
from pgvector.psycopg import register_vector_async
from google import genai
from dotenv import load_dotenv
from google.genai import types

# 환경변수 세팅 
load_dotenv()
neon_url = os.environ.get("NEON_DB_URL") 
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

# 구글 API 클라이언트 초기화
my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        base_url=my_proxy_url
    )
)
MODEL_NAME = "gemini-embedding-2-preview" 

# ==========================================
# 1. Vibe 텍스트 -> 벡터 '일괄(Batch)' 변환 함수
# ==========================================
async def get_vibe_vectors_batch(texts: list[str]) -> dict:
    """여러 개의 바이브 텍스트를 한 번의 API 통신으로 임베딩합니다."""
    # 빈 문자열이나 None은 걸러내고 유효한 텍스트만 추출
    valid_texts = [t for t in texts if t and t.strip()]
    if not valid_texts:
        return {}

    try:
        print(f"{len(valid_texts)}개의 바이브 텍스트를 한 번에 임베딩합니다...")
        # 동기식 API 호출을 방어하기 위해 스레드 풀로 넘김
        response = await asyncio.to_thread(
            client.models.embed_content,
            model=MODEL_NAME,
            contents=valid_texts, # 배열을 통째로 넘김!
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        
        # 반환된 임베딩 결과를 원본 텍스트와 매핑하여 딕셔너리로 만듦
        return {text: emb.values for text, emb in zip(valid_texts, response.embeddings)}
        
    except Exception as e:
        print(f"임베딩 일괄 생성 실패: {e}")
        return {}

# ==========================================
# 2. 비동기 일괄 DB Insert 함수
# ==========================================
async def insert_items_to_db(user_id: str, source_url: str, extracted_items: list, conn=None):
    if not extracted_items:
        return

    # 1. 바이브 텍스트 벡터화
    vibe_texts = [item.get("vibe_text", "") for item in extracted_items]
    vector_map = await get_vibe_vectors_batch(vibe_texts)

    try:
        # 2. 외부에서 conn을 넘겨받지 않았다면 새로 연결 (유연성 확보)
        # 만약 pool에서 관리하는 conn을 넘겨받는다면 context manager를 쓰지 않도록 주의
        
        # DB 커넥션에 벡터 타입 등록 (필요 시)
        await register_vector_async(conn)
        
        async with conn.cursor() as cursor:
            insert_query = """
                INSERT INTO saved_posts 
                (user_id, source_url, title, category, summary_text, image_url, vibe_text, vibe_vector, facts, reviews)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url, title) DO NOTHING; 
            """

            # 3. DB 데이터 준비
            batch_data = []
            for item in extracted_items:
                vibe_text = item.get("vibe_text", "")
                vibe_vector = vector_map.get(vibe_text)
                
                facts_data = item.get("facts", {})
                # reviews 데이터가 문자열일 경우를 대비해 딕셔너리로 강제 변환
                reviews_data = item.get("reviews")
                if isinstance(reviews_data, str):
                    reviews_data = {"core_summary": reviews_data, "star_review": ""}
                elif not reviews_data:
                    reviews_data = {}

                title = facts_data.get("title", "Unknown Item")
                
                batch_data.append((
                    str(user_id), 
                    source_url, 
                    title,         
                    item.get("category"), 
                    item.get("summary_text"),
                    item.get("image_url") or item.get("local_path") or "",
                    vibe_text, 
                    vibe_vector, 
                    facts_data,
                    reviews_data
                ))

            # 4. 일괄 실행
            await cursor.executemany(insert_query, batch_data)
            # await conn.commit()  # 호출부에서 commit을 관리하므로 여기서는 생략 가능하지만 안전을 위해 두셔도 됩니다.
            
        print(f"DB 저장 완료: {len(extracted_items)}개 아이템")
        
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")
        raise e # 에러를 상위로 던져서 상위에서 rollback 처리하게 함