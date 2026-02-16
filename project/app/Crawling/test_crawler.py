import json
import os
import requests
from playwright.sync_api import sync_playwright

# 우리가 분리해둔 크롤러 모듈에서 함수를 불러옵니다
from instagram_crawler import crawl_instagram_post

def download_images(image_urls: list, save_dir: str = "insta_vibes"):
    """
    이미지 URL 리스트를 받아 지정된 폴더에 순서대로 다운로드합니다.
    """
    if not image_urls:
        print("⚠️ 다운로드할 이미지가 없습니다.")
        return

    # 폴더가 없으면 생성
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"📁 [{save_dir}] 폴더를 새로 생성했습니다.")

    print(f"\n⬇️ 총 {len(image_urls)}장의 이미지 다운로드를 시작합니다...")

    for index, url in enumerate(image_urls):
        try:
            # 이미지 데이터 가져오기 (requests 사용)
            response = requests.get(url, timeout=10)
            response.raise_for_status() 

            # 파일명 지정 (예: image_01.jpg)
            file_name = f"image_{index + 1:02d}.jpg"
            file_path = os.path.join(save_dir, file_name)

            # 파일로 저장 (바이너리 쓰기 모드 'wb')
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            print(f"  ✅ {file_name} 저장 완료")

        except Exception as e:
            print(f"  ❌ {index + 1}번째 이미지 다운로드 실패: {e}")

    print("🎉 모든 이미지 다운로드가 완료되었습니다!\n")


def main():
    test_url = "https://www.instagram.com/p/DNSF5jryTof/"
    
    # 🔥 사용자님의 실제 쿠키 값
    SESSION_ID = "66800932735%3AkVPzTn1cdOCvwk%3A21%3AAYifS7X9eYVuTGD36Dxeoihm_bnJu2Npi8xzz1MIUw"

    with sync_playwright() as p:
        print("🚀 Playwright 브라우저 시작...")
        
        # 스텔스 모드의 핵심 옵션들
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu", 
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled" # 봇 탐지 방지
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 1024}
        )

        # 🍪 정상적인 쿠키 주입 로직
        if SESSION_ID:
            context.add_cookies([{
                "name": "sessionid",
                "value": SESSION_ID,
                "domain": ".instagram.com",
                "path": "/",
                "httpOnly": True,
                "secure": True
            }])
            print("🍪 세션 쿠키가 성공적으로 주입되었습니다.")
        else:
            print("⚠️ 경고: sessionid가 설정되지 않았습니다.")

        page = context.new_page()
        
        # 🌟 네이티브 스텔스 코드 주입 (웹드라이버 흔적 지우기)
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"🔍 [{test_url}] 데이터 수집 중...")
        
        # 크롤링 함수 실행
        result = crawl_instagram_post(page, test_url)

        print("\n✅ 크롤링 결과:")
        print(json.dumps(result, indent=4, ensure_ascii=False))

        # 에러 없이 정상적으로 데이터를 가져왔다면?
        if not result["error"]:
            page.screenshot(path="success.png")
            print("📸 성공 화면을 'success.png'로 저장했습니다.")
            
            # 👇 핵심: 추출한 URL들을 방금 만든 다운로드 함수로 넘겨줍니다!
            if result.get("image_urls"):
                download_images(result["image_urls"], save_dir="insta_vibes")

        browser.close()
        print("🛑 브라우저를 안전하게 종료했습니다.")

if __name__ == "__main__":
    main()