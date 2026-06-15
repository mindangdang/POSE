import requests
from bs4 import BeautifulSoup
import os
import json
import psycopg
from project.backend.app.utils.settings import load_backend_env

load_backend_env()
neon_url = os.environ.get("NEON_DB_URL")

if not neon_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def fetch_empty_brands():
    BASE_URL = "https://empty.seoul.kr"
    url = BASE_URL + "/brand-list.html"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    brands = []

    elements = soup.select("li.menu > a.view")

    for el in elements:
        name = el.get_text(strip=True)
        link = el.get("href")

        if not name or not link:
            continue

        full_link = BASE_URL + link if link.startswith("/") else link

        try:
            cate_no = link.split("/")[-2]
        except:
            cate_no = None

        brands.append({
            "brand_name": name,
            "brand_name_eng": "",
            "link": full_link,
        })

    return brands

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
    
    # 2. 무신사 브랜드 데이터 크롤링
    brands_list = fetch_empty_brands()
    
    # 3. DB에 데이터 저장
    insert_brands_to_db(brands_list)