import os
from psycopg.types.json import Json
from project.backend.app.core.settings import load_backend_env
import httpx

# 환경변수 세팅
load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")
GPU_SERVER_URL = os.environ.get("GPU_SERVER_URL")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")
if not GPU_SERVER_URL:
    raise ValueError(".env 파일에 GPU_SERVER_URL이 설정되지 않았습니다.")

async def _extract_vector_sync(image_url: str, category: str):
    payload = {"image_url": image_url,"category": category}
    
    try:
        # GPU 연산 및 다운로드 시간을 고려하여 넉넉한 timeout 설정
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GPU_SERVER_URL}/embedding", json=payload, timeout=15.0)

        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return
            
        # 2. GPU 서버가 계산해준 768차원 배열 획득
        image_vector = response.json().get("vector")
        if not image_vector:
            return
        
        return image_vector
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        return
# ==========================================
# 2. 비동기 일괄 DB Insert 함수
# ==========================================
async def insert_items_to_db(user_id: str, source_url: str, extracted_items: list, conn):
    if not extracted_items:
        return
    if conn is None:
        raise ValueError("Database connection is required to insert items.")
    try:
        # 2. 외부에서 conn을 넘겨받지 않았다면 새로 연결 (유연성 확보)
        # 만약 pool에서 관리하는 conn을 넘겨받는다면 context manager를 쓰지 않도록 주의
        
        async with conn.cursor() as cursor:
            insert_query = """
                INSERT INTO saved_posts 
                (user_id, source_url, title, category, sub_category, image_url, recommend, image_vector, facts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url, title) DO NOTHING; 
            """

            # 3. DB 데이터 준비
            batch_data = []
            for item in extracted_items:
                recommend = item.get("recommend", "")
                sub_category = item.get("sub_category", "")
                category = item.get("category", "")
                facts_data = item.get("facts", {})
                title = facts_data.get("title", "Unknown Item")
                image_url = item.get("image_url") or item.get("local_path") or ""

                # 이미지 벡터 추출
                vector_list = await _extract_vector_sync(image_url, sub_category)
                vector_str = str(vector_list) if vector_list else None
                
                batch_data.append((
                    str(user_id), 
                    source_url, 
                    title,         
                    category, 
                    sub_category,
                    image_url,
                    recommend, 
                    vector_str, 
                    Json(facts_data)
                ))

            # 4. 일괄 실행
            await cursor.executemany(insert_query, batch_data)
            # await conn.commit()  
            
        print(f"DB 저장 완료: {len(extracted_items)}개 아이템")
        
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")
        raise e # 에러를 상위로 던져서 상위에서 rollback 처리하게 함
