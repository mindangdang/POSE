import json
from playwright.sync_api import sync_playwright
from instagram_llm import extract_fact_and_vibe
from instagram_crawler import crawl_instagram_post, download_images
from insert_db import insert_items_to_db

def main():
    test_url = "https://www.instagram.com/p/DNSF5jryTof/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA=="
    SESSION_ID = "66800932735%3AO0JTAaKlyNOSjn%3A10%3AAYhuslDRMAGn4gJbwgPKtScrri84JWQRn4comuyXcA" 

    with sync_playwright() as p:
        print("🚀 [Step 1] Playwright 크롤러 시작...")
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 1024}
        )
        if SESSION_ID:
            context.add_cookies([{"name": "sessionid", "value": SESSION_ID, "domain": ".instagram.com", "path": "/", "httpOnly": True, "secure": True}])

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 1️⃣ 크롤링 실행
        crawl_result = crawl_instagram_post(page, test_url)
        browser.close()

        if crawl_result["error"]:
            print(f"❌ 크롤링 실패: {crawl_result['error']}")
            return

        print(f"\n✅ [Step 1 완료] 크롤링 성공! (캡션: {crawl_result['caption'][:20]}...)") 

        # 2️⃣ 이미지 다운로드
        print("\n🚀 [Step 2] 이미지 다운로드 시작...")
        downloaded_files = download_images(crawl_result["image_urls"], save_dir="insta_vibes") 

        # 3️⃣ AI 분석 실행 
        if downloaded_files:
            print("\n🚀 [Step 3] AI 데이터 추출 시작...")
            target_images = downloaded_files
            
            ai_result = extract_fact_and_vibe(
                image_paths=target_images, 
                caption=crawl_result["caption"],  
                hashtags=crawl_result["hashtags"] 
            )
            
            print("\n" + "="*50)
            print("🎯 [최종 DB 적재용 AI 분석 결과]")
            print("="*50)
            print(json.dumps(ai_result, ensure_ascii=False, indent=2))
            print("="*50)

            print("\n🚀 [Step 4] Neon DB 데이터 적재 시작...")
            
            # Pydantic 결과물에서 리스트 형태의 데이터만 추출
            extracted_items = ai_result.get("extracted_items", [])
            
            if extracted_items:
                # 테스트용 유저 ID (나중에 실제 로그인 유저 ID로 대체)
                test_user_id = "mindangdang_01" 
                
                # insert_db.py의 함수 실행 (알아서 임베딩 API 호출 후 DB에 INSERT)
                insert_items_to_db(test_user_id, test_url, extracted_items)
                
                print("\n🎉 [End-to-End 성공] 데이터 수집부터 DB 적재까지 완벽하게 끝났습니다!")
            else:
                print("⚠️ DB에 적재할 유의미한 아이템이 분석되지 않았습니다.")
        else:
            print("⚠️ 분석할 이미지가 없습니다.")

if __name__ == "__main__":
    main()