import os
from project.backend.app.manage.settings import load_backend_env
import httpx

# 환경변수 세팅
load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")
GPU_SERVER_URL = os.environ.get("GPU_SERVER_URL")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

if not GPU_SERVER_URL:
    raise ValueError(".env 파일에 GPU_SERVER_URL이 설정되지 않았습니다.")

async def _extract_vector_sync(image_url: str):
    payload = {"image_url": image_url}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GPU_SERVER_URL}/embedding", json=payload, timeout=15.0)

        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return
            
        image_vector = response.json().get("vector")
        if not image_vector:
            return
        
        return image_vector
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        return

async def insert_items_to_db(user_id: str, source_url: str, extracted_items: list, conn):
    if not extracted_items:
        return
    if conn is None:
        raise ValueError("Database connection is required to insert items.")
    try:
        
        async with conn.cursor() as cursor:
            insert_query = """
                INSERT INTO saved_posts 
                (user_id, source_url, title, price, brand, category, is_available, image_url, image_vector, shop)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url, title) DO NOTHING; 
            """
            batch_data = []
            for item in extracted_items:
                title = item.get("title", "Unknown")
                price = item.get("price")
                if price is None:
                    price = item.get("price_info") or item.get("price", "가격 미상")
                brand = item.get("brand") or item.get("shop") or "알 수 없는 브랜드"
                category = item.get("category") or "PRODUCT"
                is_available = str(item.get("is_available", "알 수 없음"))
                shop = item.get("shop") or item.get("source") or "알 수 없는 쇼핑몰"

                image_url = item.get("image_url") or item.get("local_path") or ""
                vector_list = await _extract_vector_sync(image_url)
                vector_str = str(vector_list) if vector_list else None

                batch_data.append((
                    str(user_id), 
                    source_url, 
                    title,
                    price,
                    brand,
                    category,
                    is_available,
                    image_url,
                    vector_str,
                    shop,
                ))

            await cursor.executemany(insert_query, batch_data)            
        print(f"DB 저장 완료: {len(extracted_items)}개 아이템")
        
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")
        raise e 
