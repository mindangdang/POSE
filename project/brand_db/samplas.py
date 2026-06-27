import requests
from bs4 import BeautifulSoup
import psycopg
from project.backend.app.manage.settings import get_settings

neon_url = get_settings().neon_db_url

if not neon_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def fetch_samplas_brands():
    """SAMPLAS 브랜드 리스트를 크롤링하여 가져옵니다."""
    print(" SAMPLAS 브랜드 데이터 가져오는 중...")
    BASE_URL = "https://samplas.co.kr"
    url = BASE_URL + "/brand.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        brands = []
        items = soup.select("div.brand_con")

        for item in items:
            # 이미지에 걸려 있는 브랜드 상세 페이지/상품 리스트 링크를 추출합니다.
            a_tag = item.select_one(".brand_image a")
            if not a_tag:
                continue

            link = a_tag.get("href")
            full_link = BASE_URL + link if link.startswith("/") else link

            # 👉 브랜드명 (한글/영문 분리 시도)
            name_tag = item.select_one(".brand_dec p")
            if not name_tag:
                continue

            raw_texts = name_tag.get_text("\n", strip=True).split("\n")
            name = raw_texts[0].strip()
            name_eng = raw_texts[1].strip() if len(raw_texts) > 1 else ""

            brands.append({
                "brand_name": name,
                "brand_name_eng": name_eng,
                "link": full_link,
            })
        return brands
    except Exception as e:
        print(f" 브랜드 데이터 가져오기 실패: {e}")
        return []

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
                brand_tuples = [(b['brand_name'], b['brand_name_eng'], b['link']) for b in brands]
                cursor.executemany(insert_query, brand_tuples)
                conn.commit()
                print(" 브랜드 데이터 삽입 성공!")
    except Exception as e:
        print(f" 데이터 삽입 중 에러 발생: {e}")

if __name__ == "__main__":
    brands_list = fetch_samplas_brands()
    insert_brands_to_db(brands_list)
