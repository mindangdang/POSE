import requests
import time
import os
import json
import psycopg
from project.backend.app.utils.settings import load_backend_env

load_backend_env()
neon_url = os.environ.get("NEON_DB_URL")

if not neon_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def fetch_musinsa_brands():
    """무신사 브랜드 리스트 JSON 데이터를 가져옵니다."""
    print(" 무신사 브랜드 데이터 가져오는 중...")
    url = f"https://static.msscdn.net/display/brand/brand-list.json?v={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        
        brands = []
        for brand in data:
            brands.append({
                "brand_name": brand.get("name"),
                "brand_name_eng": brand.get("englishName"),
                "link": brand.get("linkUrl"),
            })
        return brands
    except Exception as e:
        print(f" 브랜드 데이터 가져오기 실패: {e}")
        return []

def initialize_database():
    print(" Neon DB에 연결 중입니다...")
    conn = None
    cursor = None
    
    try:
        # DB 연결 및 커서 생성
        conn = psycopg.connect(neon_url)
        cursor = conn.cursor()

        # 1. 브랜드 정보 테이블 생성
        print(" brands 테이블 생성 중...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS brands (
            id SERIAL PRIMARY KEY,
            brand_name TEXT NOT NULL,
            brand_name_eng TEXT,
            keywords TEXT,
            link TEXT,
            target_group TEXT,
            mean_price TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(brand_name, link)
        );
        """
        cursor.execute(create_table_query)

        # 작업 확정
        conn.commit()
        print("데이터베이스 스키마 세팅이 완벽하게 완료되었습니다!")

    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
            
    finally:
        # 연결 안전하게 종료
        if cursor: cursor.close()
        if conn: conn.close()
        print(" DB 연결을 종료했습니다.")

def insert_brands_to_db(brands):
    """수집된 브랜드 데이터를 DB에 삽입합니다."""
    if not brands:
        print(" 삽입할 브랜드 데이터가 없습니다.")
        return

    print(f" {len(brands)}개 브랜드 데이터 DB 삽입 시작...")
    try:
        with psycopg.connect(neon_url) as conn:
            with conn.cursor() as cursor:
                insert_query = """
                INSERT INTO brands (brand_name, brand_name_eng, link)
                VALUES (%s, %s, %s)
                ON CONFLICT (brand_name, link) DO NOTHING;
                """
                
                # 데이터를 튜플 리스트로 변환 (JSON 데이터는 json.dumps로 직렬화)
                brand_tuples = [
                    (b['brand_name'], b['brand_name_eng'], b['link'])
                    for b in brands
                ]
                
                cursor.executemany(insert_query, brand_tuples)
                conn.commit()
                print(" 브랜드 데이터 삽입이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f" 데이터 삽입 중 에러 발생: {e}")

if __name__ == "__main__":
    # 1. DB 스키마 초기화
    initialize_database()
    
    # 2. 무신사 브랜드 데이터 크롤링
    brands_list = fetch_musinsa_brands()
    
    # 3. DB에 데이터 저장
    insert_brands_to_db(brands_list)
