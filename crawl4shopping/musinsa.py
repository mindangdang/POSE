import asyncio
import json
import os
import nodriver as uc
from bs4 import BeautifulSoup
import traceback
from decimal import Decimal, InvalidOperation
from curl_cffi import requests as curl_requests
import asyncpg
from pgvector.asyncpg import register_vector
import httpx
from project.backend.app.manage.settings import get_settings
from project.backend.basic_functions.utils import _extract_vector_batch, _extract_text_vector_batch
from project.backend.basic_functions.crawlers.utils import text_translate, get_clean_category

neon_db_url = get_settings().neon_db_url

if not neon_db_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

PROGRESS_FILE = "crawler_progress.json"

def load_progress() -> set:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ 진행 상태 파일을 읽는 중 오류 발생: {e}. 새로 시작합니다.")
            return set()
    return set()

def save_progress(completed_urls: set):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(completed_urls), f)

def parse_price(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(',', '')
    if not normalized:
        return None
    digits = ''.join(ch for ch in normalized if ch.isdigit() or ch in {'.', '-'})
    if not digits or digits in {'.', '-'}:
        return None
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def parse_is_soldout(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', 't', '1', 'yes', 'y'}:
            return True
        if normalized in {'false', 'f', '0', 'no', 'n'}:
            return False
    return None

# --- Worker 1: Producer (크롤러) ---
async def crawler_worker(url, raw_data_queue):
    """
    무신사 페이지에서 SSR 데이터 및 API를 순회하며 
    원시 데이터(JSON list)만 수집하여 raw_data_queue에 넘깁니다.
    """
    config = uc.Config(
        headless=True,
        no_sandbox=True,
        browser_executable_path="/usr/bin/google-chrome",
        browser_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1920,1080",
            "--disable-gpu"
        ]
    )
    
    try:
        browser = await uc.start(config=config)
    except Exception:
        traceback.print_exc()
        await raw_data_queue.put(None)
        raise

    page = await browser.get(url)
    print("[1] 무신사 페이지 접속 및 SSR 렌더링 대기 중...")
    await asyncio.sleep(4)
    
    print("[2] SSR 초기 데이터 추출 중...")
    html = await page.get_content()
    soup = BeautifulSoup(html, 'html.parser')
    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    
    if not next_data_tag:
        print("❌ SSR 데이터를 찾을 수 없습니다.")
        browser.stop()
        await raw_data_queue.put(None)
        return

    try:
        json_data = json.loads(next_data_tag.string)
        queries = json_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        
        initial_page_data = None
        for q in queries:
            state_data = q.get('state', {}).get('data', {})
            if 'pages' in state_data:
                initial_page_data = state_data['pages'][0]
                break
                
        if not initial_page_data:
            print("❌ 상품 리스트 데이터를 찾을 수 없습니다.")
            browser.stop()
            await raw_data_queue.put(None)
            return
            
        items = initial_page_data.get('data', {}).get('list', [])
        next_url = initial_page_data.get('data', {}).get('pagination', {}).get('nextPageUrl')
        
    except Exception as e:
        print(f"❌ JSON 파싱 에러: {e}")
        browser.stop()
        await raw_data_queue.put(None)
        return

    print(f"📥 [페이지 1] 원시 데이터 수집 완료: {len(items)}개 -> 벡터화 대기열 전송")
    await raw_data_queue.put(items)
    total_collected = len(items)
    
    print("[3] 브라우저 인증 정보 추출 및 API 세션 구성 중...")
    ua = await page.evaluate("navigator.userAgent")
    cookies_str = await page.evaluate("document.cookie")
    browser.stop()
    
    session = curl_requests.Session(impersonate="chrome")
    session.headers.update({
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookies_str,
        "Referer": "https://www.musinsa.com/"
    })
    
    page_count = 2
    while next_url:
        print(f"\n[4] [페이지 {page_count}] API 직접 호출 중...")
        try:
            response = session.get(next_url)
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                break

            response_json = response.json()
            if "data" not in response_json:
                print("❌ data 필드 없음")
                break

            new_items = response_json["data"].get("list", [])
            if not new_items:
                break
                
            await raw_data_queue.put(new_items)
            total_collected += len(new_items)
            print(f"📥 [페이지 {page_count}] {len(new_items)}개 원시 데이터 수집 -> 벡터화 대기열 전송")
            
            next_url = response_json["data"].get("pagination", {}).get("nextPageUrl")
            page_count += 1
            await asyncio.sleep(1.5)

        except Exception:
            traceback.print_exc()
            break

    await raw_data_queue.put(None)
    print(f"\n🎉 [크롤링 완료] 원시 데이터 총 {total_collected}개 수집 완료. 벡터화 잔여 작업 대기 중...")

# --- Worker 2: Processor (가공 및 벡터화) ---
async def processor_worker(raw_data_queue, db_insert_queue):
    """
    raw_data_queue에서 원시 데이터를 꺼내어 배치(Batch)로 벡터를 추출한 뒤,
    DB 적재용 튜플로 변환하여 db_insert_queue에 넘깁니다.
    """
    # 글로벌 클라이언트 하나를 재사용하여 네트워크 오버헤드 방지
    async with httpx.AsyncClient() as client:
        while True:
            items = await raw_data_queue.get()
            
            if items is None:
                # 크롤러 종료 시그널을 받으면 DB 워커에게도 종료 시그널 전달
                await db_insert_queue.put(None)
                raw_data_queue.task_done()
                break
                
            # 배치 처리를 위한 데이터 분리
            titles = [item.get('goodsName', '') for item in items]
            image_urls = [item.get('thumbnail') for item in items]
            translated_titles = [text_translate(title, 'en') for title in titles]
            
            # [수정] 텍스트와 이미지 배치를 동시에 추출 (I/O 병렬화)
            title_vectors, image_vectors = await asyncio.gather(
                _extract_text_vector_batch(translated_titles, client),
                _extract_vector_batch(image_urls, client)
            )
            
            records = []
            for i, item in enumerate(items):
                source_url = item.get('goodsLinkUrl')
                if not source_url:
                    continue
                title = titles[i] or 'Unknown'
                price = parse_price(item.get('price') or item.get('normalPrice'))
                currency = 'KRW'
                brand = item.get('brand') or 'UNKNOWN'
                is_soldout = parse_is_soldout(item.get('isSoldOut'))
                image_url = image_urls[i] or ''
                shop = 'MUSINSA'
                gender = item.get('displayGenderText') or 'UNKNOWN'
                
                # 원본 결과가 이중 리스트일 수 있으므로 안전하게 벗김
                raw_title_vec = title_vectors[i]
                if raw_title_vec and isinstance(raw_title_vec, list) and isinstance(raw_title_vec[0], list):
                    title_vector = raw_title_vec[0]
                else:
                    title_vector = raw_title_vec
                category = get_clean_category(title_vector) or 'PRODUCT'
                image_vector = image_vectors[i]

                records.append((
                    source_url, title, title_vector, price, currency, brand, category,
                    is_soldout, image_url, image_vector, shop, gender
                ))
            
            await db_insert_queue.put(records)
            raw_data_queue.task_done()
            print(f"🔄 [가공 완료] {len(records)}개 데이터 벡터 추출 완료 -> DB 큐 전송")

# --- Worker 3: Consumer (DB 적재) ---
async def db_worker(db_insert_queue, pool):
    insert_query = """
        INSERT INTO product_db
        (
            source_url, title, title_vector, price, currency, brand, category,
            is_soldout, image_url, image_vector, shop_id, gender
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            (SELECT id FROM shops WHERE name = $11),
            $12
        )
        ON CONFLICT (source_url) DO UPDATE SET
            title = EXCLUDED.title,
            title_vector = COALESCE(EXCLUDED.title_vector, product_db.title_vector),
            price = EXCLUDED.price,
            currency = EXCLUDED.currency,
            brand = EXCLUDED.brand,
            category = EXCLUDED.category,
            is_soldout = EXCLUDED.is_soldout,
            image_url = EXCLUDED.image_url,
            image_vector = COALESCE(EXCLUDED.image_vector, product_db.image_vector),
            shop_id = EXCLUDED.shop_id,
            gender = EXCLUDED.gender;
    """
    
    while True:
        batch_data = await db_insert_queue.get()
        
        if batch_data is None:
            db_insert_queue.task_done()
            break
            
        try:
            async with pool.acquire() as conn:
                await conn.executemany(insert_query, batch_data)
            print(f"✅ DB 삽입 완료: {len(batch_data)}건 시도 (중복 제외 삽입됨)")
        except Exception as e:
            print(f"❌ DB 처리 중 에러 발생: {e}")
        finally:
            db_insert_queue.task_done()

async def init_db_connection(conn):
    await register_vector(conn)

url_list = [
    "https://www.musinsa.com/category/001001/goods?gf=A",
    "https://www.musinsa.com/category/001002/goods?gf=A",
    "https://www.musinsa.com/category/001010/goods?gf=A",
    "https://www.musinsa.com/category/001003/goods?gf=A",
    "https://www.musinsa.com/category/001011/goods?gf=A",
    "https://www.musinsa.com/category/001006/goods?gf=A",
    "https://www.musinsa.com/category/001005/goods?gf=A",
    "https://www.musinsa.com/category/001008/goods?gf=A",
    "https://www.musinsa.com/category/001004/goods?gf=A"
]

async def main():
    print("🔌 DB 커넥션 풀 생성 중...")
    pool = await asyncpg.create_pool(
        neon_db_url, 
        min_size=1, 
        max_size=10, 
        setup=init_db_connection
    )
    
    completed_urls = load_progress()
    print(f"📊 현재까지 완료된 카테고리 수: {len(completed_urls)} / {len(url_list)}")

    try:
        for index, target_url in enumerate(url_list, start=1):
            if target_url in completed_urls:
                print(f"⏭️  [{index}/{len(url_list)}] 이미 처리된 URL입니다. 건너뜁니다: {target_url}")
                continue
                
            print(f"\n▶️ [{index}/{len(url_list)}] 작업을 시작합니다: {target_url}")
            
            # 파이프라인 버퍼 설정 (메모리 제어 목적)
            raw_data_queue = asyncio.Queue(maxsize=10)
            db_insert_queue = asyncio.Queue(maxsize=10)
            
            # [수정] 3개의 워커 태스크 생성
            crawler_task = asyncio.create_task(crawler_worker(target_url, raw_data_queue))
            processor_task = asyncio.create_task(processor_worker(raw_data_queue, db_insert_queue))
            db_task = asyncio.create_task(db_worker(db_insert_queue, pool))
            
            # 3개의 태스크가 모두 종료될 때까지 대기
            await asyncio.gather(crawler_task, processor_task, db_task)
            
            completed_urls.add(target_url)
            save_progress(completed_urls)
            print(f"✅ [{index}/{len(url_list)}] 처리가 성공적으로 종료되어 상태를 저장했습니다.\n")
            
    finally:
        await pool.close()
        print("🔌 DB 커넥션 풀 종료됨.")

if __name__ == '__main__':
    asyncio.run(main())
'''
python -m crawl4shopping.musinsa
chromium --headless --disable-gpu --dump-dom https://www.google.com
'''