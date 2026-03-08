import json
import os
from playwright.sync_api import sync_playwright
from project.backend.Step1.image_ocr_llm import extract_fact_and_vibe
from project.backend.Step1.instagram_crawler import crawl_instagram_post, download_images
from project.backend.Step1.insert_db import insert_items_to_db

def main():
    test_url = "https://www.instagram.com/p/DNSF5jryTof/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA=="
    STATE_FILE = "instagram_state.json"

    with sync_playwright() as p:
        print("🚀 [Step 1] Playwright 크롤러 시작...")
        
        # 세션 파일 존재 여부에 따라 Headless 모드 자동 결정
        # 파일이 있으면 True(화면 숨김), 없으면 직접 로그인을 위해 False(화면 표시)
        is_headless = os.path.exists(STATE_FILE)

        browser = p.chromium.launch(
            headless=is_headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        
        # 공통 Context 옵션 (봇 탐지 우회를 위한 User-Agent 등 그대로 유지)
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "locale": "ko-KR",
            "viewport": {"width": 1280, "height": 1024}
        }

        # 1️⃣ 로그인 상태 분기 처리
        if is_headless:
            print(f"✅ 저장된 로그인 상태({STATE_FILE})를 불러와 백그라운드로 실행합니다...")
            context_options["storage_state"] = STATE_FILE
            context = browser.new_context(**context_options)
            page = context.new_page()
        else:
            print("⚠️ 저장된 로그인 상태가 없습니다. 브라우저가 열리면 인스타그램 로그인을 진행해주세요.")
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            page.goto("https://www.instagram.com/accounts/login/")
            # 사용자가 로그인을 마칠 때까지 콘솔에서 대기
            input("👉 브라우저에서 로그인을 완전히 마친 후, 이 콘솔 창에서 [Enter] 키를 눌러주세요...")
            
            # 로그인 완료 후 세션 상태 저장
            context.storage_state(path=STATE_FILE)
            print(f"✅ 로그인 상태가 '{STATE_FILE}'에 저장되었습니다. 다음부터는 백그라운드(Headless)로 자동 진행됩니다.")

        # 봇 탐지 우회 스크립트 주입
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 크롤링 실행
        crawl_result = crawl_instagram_post(page, test_url)
        browser.close() # 크롤링이 끝났으므로 브라우저 종료

        # 에러 핸들링
        if crawl_result.get("error"):
            print(f"❌ 크롤링 실패: {crawl_result['error']}")
            return

        caption_preview = crawl_result['caption'][:20] if crawl_result['caption'] else "없음"
        print(f"\n✅ [Step 1 완료] 크롤링 성공! (캡션: {caption_preview}...)") 

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