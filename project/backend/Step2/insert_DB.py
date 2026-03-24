import os
import json
import asyncio
import psycopg 
from pgvector.psycopg import register_vector 
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
async def insert_items_to_db(user_id: str, source_url: str, extracted_items: list):
    if not extracted_items:
        return

    # 1. 파싱된 아이템들에서 vibe_text만 모아서 한 번에 벡터화
    vibe_texts = [item.get("vibe_text", "") for item in extracted_items]
    vector_map = await get_vibe_vectors_batch(vibe_texts)

    try:
        # 2. psycopg3 비동기 커넥션 연결
        async with await psycopg.AsyncConnection.connect(neon_url) as conn:
            # DB 커넥션에 벡터 타입 등록
            await register_vector(conn) 
            
            async with conn.cursor() as cursor:
                insert_query = """
                    INSERT INTO saved_posts 
                    (user_id, source_url, title, category, summary_text, image_url, vibe_text, vibe_vector, facts, reviews)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_url, title) DO NOTHING; 
                """

                # 3. DB에 넣을 데이터를 배열로 준비
                batch_data = []
                for item in extracted_items:
                    vibe_text = item.get("vibe_text", "")
                    vibe_vector = vector_map.get(vibe_text) # 미리 API로 받아온 벡터값 꺼내기
                    
                    facts_data = item.get("facts", {})
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
                        json.dumps(facts_data, ensure_ascii=False),
                        json.dumps(item.get("reviews", {}), ensure_ascii=False)
                    ))

                # 4. executemany로 한 번의 통신으로 모든 데이터 밀어넣기
                await cursor.executemany(insert_query, batch_data)
            
            # 커밋
            await conn.commit()
            
        print(f" DB 저장 완료: {len(extracted_items)}개의 아이템이 한 번에 처리됨")
        
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")