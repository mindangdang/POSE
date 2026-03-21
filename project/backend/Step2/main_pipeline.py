import json
from playwright.sync_api import sync_playwright

# 작성해두신 외부 모듈들 임포트
from image_ocr_llm import extract_fact_and_vibe
from project.backend.Step1.instagram_crawler import crawl_instagram_post, download_images
from insert_DB import insert_items_to_db

def main():
    test_url = "https://www.instagram.com/p/DUzxRvJkRAe/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA=="
    SESSION_ID = "66800932735%3AipxCFPe78VNOb1%3A5%3AAYiH46rE0IN3QWxFHiLUGPssIuxLkFIb3-GD4p1Cuw" 

    with sync_playwright() as p:
        print(" [Step 1] Playwright 크롤러 시작...")
        
        # Dev Container(Linux 서버) 환경에 맞춘 최적화 옵션 (무조건 headless=True)
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--single-process",
                "--disable-software-rasterizer",
                "--disable-extensions"
            ]
        )
        
        # 봇 탐지 우회를 위한 User-Agent 및 환경 설정
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 1024}
        )
        
        if SESSION_ID:
            context.add_cookies([{
                "name": "sessionid", 
                "value": SESSION_ID, 
                "domain": ".instagram.com", 
                "path": "/", 
                "httpOnly": True, 
                "secure": True
            }])

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 크롤링 실행
        crawl_result = crawl_instagram_post(page, test_url)
        browser.close()

        if crawl_result.get("error"):
            print(f"크롤링 실패: {crawl_result['error']}")
            return

        caption_preview = crawl_result['caption'][:20] if crawl_result['caption'] else "없음"
        print(f"\n[Step 1 완료] 크롤링 성공! (캡션: {caption_preview}...)") 

        # 이미지 다운로드
        print("\n[Step 2] 이미지 다운로드 시작...")
        downloaded_files = download_images(crawl_result["image_urls"], save_dir="insta_vibes") 

        # AI 분석 및 DB 적재 실행 
        if downloaded_files:
            print("\n [Step 3] AI 데이터 추출 시작...")
            
            ai_result = extract_fact_and_vibe(
                image_paths=downloaded_files, 
                caption=crawl_result["caption"],  
                hashtags=crawl_result["hashtags"] 
            )
            
            print("\n" + "="*50)
            print("[최종 DB 적재용 AI 분석 결과]")
            print("="*50)
            print(json.dumps(ai_result, ensure_ascii=False, indent=2))
            print("="*50)

            print("\n[Step 4] Neon DB 데이터 적재 시작...")
            
            extracted_items = ai_result.get("extracted_items", [])
            
            if extracted_items:
                test_user_id = "mindangdang_01" 
                insert_items_to_db(test_user_id, test_url, extracted_items)
                
                print("\n[End-to-End 성공] 데이터 수집부터 DB 적재까지 완벽하게 끝났습니다!")
            else:
                print(" DB에 적재할 유의미한 아이템이 분석되지 않았습니다.")
        else:
            print("분석할 이미지가 없습니다.")

if __name__ == "__main__":
    main()