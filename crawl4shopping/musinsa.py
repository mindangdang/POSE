import asyncio
import json
import nodriver as uc
from bs4 import BeautifulSoup
import traceback
from curl_cffi import requests as curl_requests
import asyncpg

# Neon DB 접속 정보
neon_db_url = 'postgresql://neondb_owner:npg_Dro4bCcG1Ikd@ep-curly-base-aii29p7u-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require'

def extract_records(items):
    """API 응답 데이터를 DB 적재용 튜플 리스트로 변환"""
    records = []
    for item in items:
        source_url = item.get('goodsLinkUrl', None)
        title = item.get('goodsName')
        title_vector = None
        price = str(item.get('price')) or str(item.get('normalPrice'))
        brand = item.get('brand')
        category = 'top'
        is_soldout = str(item.get('isSoldOut')) 
        image_url = item.get('thumbnail') or []
        image_vector = None 
        shop = 'musinsa'
        gender = item.get('displayGenderText')

        records.append((
            source_url, title, title_vector, price, brand, 
            category, is_soldout, image_url, image_vector, shop, gender
        ))
    return records

async def db_worker(queue, pool):
    """소비자(Consumer): 큐에서 데이터를 꺼내어 DB에 비동기로 적재"""
    insert_query = """
        INSERT INTO product_db 
        (source_url, title, title_vector, price, brand, category, is_soldout, image_url, image_vector, shop, gender)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (source_url, title) DO NOTHING;
    """
    
    while True:
        batch_data = await queue.get()
        
        # 종료 시그널(None)을 받으면 루프 종료
        if batch_data is None:
            queue.task_done()
            break
            
        try:
            # 커넥션 풀에서 연결을 빌려와 executemany로 일괄 처리
            async with pool.acquire() as conn:
                await conn.executemany(insert_query, batch_data)
            print(f"✅ DB 삽입 완료: {len(batch_data)}건 처리됨")
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
        # 크롤러 실패 시 DB 워커도 종료되도록 None 전달
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

    # 1페이지 데이터 가공 및 큐에 전송
    records = extract_records(items)
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
                
            # 데이터 가공 후 DB 큐에 전송 (메모리에 누적하지 않음)
            records = extract_records(new_items)
            total_collected += len(records)
            print(f"📥 [페이지 {page_count}] {len(records)}개 수집 -> DB 큐에 전송")
            
            # 큐가 꽉 차 있으면 DB 적재가 끝날 때까지 대기하게 됨 (Backpressure 역할)
            await queue.put(records)

            next_url = response_json["data"].get("pagination", {}).get("nextPageUrl")
            page_count += 1
            
            await asyncio.sleep(1.5)

        except Exception:
            traceback.print_exc()
            break

    # 크롤링 루프 종료 후 소비자에게 종료 시그널 전달
    await queue.put(None)
    print(f"\n🎉 [크롤링 완료] 총 {total_collected}개 상품 수집 완료. DB 잔여 작업 대기 중...")

async def main():
    target_url = "https://www.musinsa.com/category/001003/goods?gf=A" # 피케/카라티
    
    # 큐 사이즈 제한 설정: 큐에 최대 5페이지 분량의 데이터만 대기 가능. 
    # 크롤링이 DB 적재보다 너무 빠를 경우 메모리 폭발을 방지합니다.
    queue = asyncio.Queue(maxsize=5)
    
    print("🔌 DB 커넥션 풀 생성 중...")
    # asyncpg 커넥션 풀 생성 (min_size, max_size로 연결 수 관리)
    pool = await asyncpg.create_pool(neon_db_url, min_size=1, max_size=10)
    
    try:
        # 크롤러(생산자)와 DB 처리(소비자)를 동시에 실행
        crawler_task = asyncio.create_task(crawler_worker(target_url, queue))
        db_task = asyncio.create_task(db_worker(queue, pool))
        
        # 두 태스크가 모두 끝날 때까지 대기
        await asyncio.gather(crawler_task, db_task)
        print("✅ 모든 프로세스가 성공적으로 종료되었습니다.")
        
    finally:
        # 종료 시 커넥션 풀 닫기
        await pool.close()
        print("🔌 DB 커넥션 풀 종료됨.")

if __name__ == '__main__':
    asyncio.run(main())

'''
google-chrome \
--headless \
--no-sandbox \
--disable-gpu \
about:blank
'''