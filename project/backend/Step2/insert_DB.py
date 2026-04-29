import os
import json
import asyncio
import psycopg 
from psycopg.types.json import Json
from PIL import Image
from project.backend.app.core.settings import load_backend_env, IMAGE_DIR
from project.backend.app.core.resilience import with_llm_resilience
from project.backend.Step3.embedding_reranking import FashionSiglipReRankingPipeline

# 환경변수 세팅 
load_backend_env()
neon_url = os.environ.get("NEON_DB_URL") 
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

def _extract_vector_sync(image_url: str, category: str):
    try:
        pipeline = FashionSiglipReRankingPipeline(lambda_weight=0.6)
        local_path = image_url
        if local_path and not local_path.startswith(('http://', 'https://')):
            local_path = os.path.join(str(IMAGE_DIR), os.path.basename(local_path))
            if os.path.exists(local_path):
                with Image.open(local_path) as img:
                    return pipeline.get_image_vector(img, category)
    except Exception as e:
        print(f"벡터 추출 에러: {e}")
    return None

# ==========================================
# 2. 비동기 일괄 DB Insert 함수
# ==========================================
async def insert_items_to_db(user_id: str, source_url: str, extracted_items: list, conn=None):
    if not extracted_items:
        return
    try:
        # 2. 외부에서 conn을 넘겨받지 않았다면 새로 연결 (유연성 확보)
        # 만약 pool에서 관리하는 conn을 넘겨받는다면 context manager를 쓰지 않도록 주의
        

        
        async with conn.cursor() as cursor:
            insert_query = """
                INSERT INTO saved_posts 
                (user_id, source_url, title, category, sub_category, summary_text, image_url, recommend, image_vector, facts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

                # 이미지 벡터 추출 (비동기 스레드 실행)
                vector_list = await asyncio.to_thread(_extract_vector_sync, image_url, sub_category or category)
                vector_str = str(vector_list) if vector_list else None
                
                batch_data.append((
                    str(user_id), 
                    source_url, 
                    title,         
                    category, 
                    sub_category,
                    item.get("summary_text"),
                    image_url,
                    recommend, 
                    vector_str, 
                    Json(facts_data)
                ))

            # 4. 일괄 실행
            await cursor.executemany(insert_query, batch_data)
            # await conn.commit()  # 호출부에서 commit을 관리하므로 여기서는 생략 가능하지만 안전을 위해 두셔도 됩니다.
            
        print(f"DB 저장 완료: {len(extracted_items)}개 아이템")
        
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")
        raise e # 에러를 상위로 던져서 상위에서 rollback 처리하게 함
