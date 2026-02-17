# 수정할 상단 Import 부분
import json
from playwright.sync_api import sync_playwright
from instagram_llm import extract_fact_and_vibe
from instagram_crawler import crawl_instagram_post, download_images

def main():
    test_url = "https://www.instagram.com/p/DNSF5jryTof/"
    SESSION_ID = "66800932735%3AUOpBmfQO7fuyAn%3A1%3AAYiIHAzu5duEZl2Fx9LgW79sWhywVtxFvJ7kM09QzA" 

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

        # 3️⃣ AI 분석 실행 (첫 번째 대표 이미지만 분석)
        if downloaded_files:
            print("\n🚀 [Step 3] AI 데이터 추출 시작...")
            target_image = downloaded_files[2] 
            
            ai_result = extract_fact_and_vibe(
                image_path=target_image, 
                caption=crawl_result["caption"], 
                hashtags=crawl_result["hashtags"]
            )
            
            print("\n" + "="*50)
            print("🎯 [최종 DB 적재용 AI 분석 결과]")
            print("="*50)
            print(json.dumps(ai_result, ensure_ascii=False, indent=2))
            print("="*50)
        else:
            print("⚠️ 분석할 이미지가 없습니다.")

if __name__ == "__main__":
    main()