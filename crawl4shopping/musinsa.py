import asyncio
import json
import os
import nodriver as uc
from bs4 import BeautifulSoup
import traceback
from curl_cffi import requests as curl_requests
import asyncpg
from pgvector.asyncpg import register_vector
from project.backend.basic_functions.utils import _extract_vector_sync, _extract_text_vector_sync
from project.backend.app.manage.settings import get_settings

neon_db_url = get_settings().neon_db_url

if not neon_db_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

PROGRESS_FILE = "crawler_progress.json"

def load_progress() -> set:
    """이전 크롤링 진행 상태를 파일에서 불러옵니다."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ 진행 상태 파일을 읽는 중 오류 발생: {e}. 새로 시작합니다.")
            return set()
    return set()

def save_progress(completed_urls: set):
    """현재까지 완료된 URL 목록을 파일에 저장합니다."""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(completed_urls), f)

async def extract_records(items):
    """API 응답 데이터를 DB 적재용 튜플 리스트로 변환"""
    records = []
    for item in items:
        source_url = item.get('goodsLinkUrl', None)
        title = item.get('goodsName')
        raw_title_vector = await _extract_text_vector_sync(title)
        price = str(item.get('price')) or str(item.get('normalPrice'))
        brand = item.get('brand')
        category = 'top'
        is_soldout = str(item.get('isSoldOut')) 
        image_url = item.get('thumbnail') or []
        image_vector = await _extract_vector_sync(image_url)
        shop = 'musinsa'
        gender = item.get('displayGenderText')

        if raw_title_vector and isinstance(raw_title_vector, list) and len(raw_title_vector) > 0 and isinstance(raw_title_vector[0], list):
            title_vector = raw_title_vector[0]  # 2중 리스트인 경우 벗김
        else:
            title_vector = raw_title_vector

        records.append((
            source_url,    # $1
            title,         # $2
            price,         # $3
            brand,         # $4
            category,      # $5
            is_soldout,    # $6
            image_url,     # $7
            image_vector,  # $8
            shop,          # $9
            gender,        # $10
            title_vector   # $11
        ))
    return records

async def db_worker(queue, pool):
    """소비자(Consumer): 큐에서 데이터를 꺼내어 DB에 비동기로 적재"""
    # [수정됨] ON CONFLICT 기준을 title 단일로 변경 (DB에 UNIQUE 제약조건 필요)
    insert_query = """
        INSERT INTO product_db 
        (source_url, title, price, brand, category, is_soldout, image_url, image_vector, shop, gender, title_vector)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (title) DO NOTHING;
    """
    
    while True:
        batch_data = await queue.get()
        
        if batch_data is None:
            queue.task_done()
            break
            
        try:
            async with pool.acquire() as conn:
                # [수정됨] register_vector는 pool 생성 시 setup에 위임했으므로 여기서 제거 (성능 대폭 향상)
                await conn.executemany(insert_query, batch_data)
            print(f"✅ DB 삽입 완료: {len(batch_data)}건 시도 (중복 제외 삽입됨)")
        except Exception as e:
            print(f"❌ DB 처리 중 에러 발생: {e}")
        finally:
            queue.task_done()

async def crawler_worker(url, queue):
    """생산자(Producer): 데이터를 크롤링하여 큐에 전달"""
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
        await queue.put(None)
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
        await queue.put(None)
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
            await queue.put(None)
            return
            
        items = initial_page_data.get('data', {}).get('list', [])
        next_url = initial_page_data.get('data', {}).get('pagination', {}).get('nextPageUrl')
        
    except Exception as e:
        print(f"❌ JSON 파싱 에러: {e}")
        browser.stop()
        await queue.put(None)
        return

    records = await extract_records(items)
    print(f"📥 [페이지 1] 수집 완료: {len(records)}개 -> DB 큐에 전송")
    await queue.put(records)
    
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
    total_collected = len(records)

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
                
            records = await extract_records(new_items)
            total_collected += len(records)
            print(f"📥 [페이지 {page_count}] {len(records)}개 수집 -> DB 큐에 전송")
            
            await queue.put(records)

            next_url = response_json["data"].get("pagination", {}).get("nextPageUrl")
            page_count += 1
            
            await asyncio.sleep(1.5)

        except Exception:
            traceback.print_exc()
            break

    await queue.put(None)
    print(f"\n🎉 [크롤링 완료] 단일 카테고리 총 {total_collected}개 상품 수집 완료. DB 잔여 작업 대기 중...")

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

async def init_db_connection(conn):
    """커넥션 풀이 생성될 때 최초 1회만 벡터 타입을 등록하기 위한 setup 함수"""
    await register_vector(conn)

async def main():
    print("🔌 DB 커넥션 풀 생성 중...")
    # [수정됨] setup 매개변수를 이용해 커넥션 맺을 때 벡터 타입을 한번만 등록하도록 최적화
    pool = await asyncpg.create_pool(
        neon_db_url, 
        min_size=1, 
        max_size=10, 
        setup=init_db_connection
    )
    
    # 진행 상태 로드
    completed_urls = load_progress()
    print(f"📊 현재까지 완료된 카테고리 수: {len(completed_urls)} / {len(url_list)}")

    try:
        for index, target_url in enumerate(url_list, start=1):
            if target_url in completed_urls:
                print(f"⏭️  [{index}/{len(url_list)}] 이미 처리된 URL입니다. 건너뜁니다: {target_url}")
                continue
                
            print(f"\n▶️ [{index}/{len(url_list)}] 작업을 시작합니다: {target_url}")
            queue = asyncio.Queue(maxsize=5)
            
            crawler_task = asyncio.create_task(crawler_worker(target_url, queue))
            db_task = asyncio.create_task(db_worker(queue, pool))
            
            await asyncio.gather(crawler_task, db_task)
            
            # 크롤러와 DB 적재가 정상 종료되면 progress 업데이트
            completed_urls.add(target_url)
            save_progress(completed_urls)
            print(f"✅ [{index}/{len(url_list)}] 처리가 성공적으로 종료되어 상태를 저장했습니다.\n")
            
    finally:
        await pool.close()
        print("🔌 DB 커넥션 풀 종료됨.")

if __name__ == '__main__':
    asyncio.run(main())