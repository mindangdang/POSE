import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 앞서 만든 크롤러 파일(instagram_crawler.py)에서 필요한 함수들을 불러옵니다.
from instagram_crawler import (
    build_chrome_stealth_args,
    apply_runtime_stealth,
    crawl_instagram_post
)

def main():
    # 1. 크롤링을 테스트할 실제 인스타그램 게시물 URL을 넣어주세요!
    test_url = "https://www.instagram.com/p/DNSF5jryTof/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==" 
    
    # 2. 스텔스 옵션 생성 및 적용
    # 2. 스텔스 옵션 생성 및 적용
    options = Options()
    chrome_args = build_chrome_stealth_args(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    for arg in chrome_args:
        options.add_argument(arg)
        
    # 👇👇 리눅스 서버 크래시 방지를 위한 필수 옵션 2개 강제 추가! 👇👇
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    
    # ❌ 절대 주석을 풀지 마세요! (코드스페이스에서는 화면을 띄울 수 없습니다)
    # options.arguments.remove("--headless=new")

    driver = None
    try:
        print("🚀 크롬 브라우저를 시작합니다...")
        driver = webdriver.Chrome(options=options)
        
        # 3. 봇 탐지 우회(Stealth) 스크립트 주입
        apply_runtime_stealth(driver)
        
        # 4. 본격적인 크롤링 시작
        print(f"🔍 [{test_url}] 데이터 수집 중... (최대 12초 대기)")
        result = crawl_instagram_post(driver, test_url)
        
        # 5. 결과물을 보기 좋게 출력
        print("\n✅ 크롤링 결과:")
        print(json.dumps(result, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
    finally:
        # 6. 작업이 끝나면 메모리 누수 방지를 위해 브라우저를 반드시 종료합니다.
        if driver:
            driver.quit()
            print("\n🛑 브라우저를 안전하게 종료했습니다.")

if __name__ == "__main__":
    main()