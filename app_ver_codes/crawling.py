import json
import requests
from urllib.parse import urlparse

def extract_instagram_data_via_api(post_url: str, session_id: str) -> dict:
    """
    Playwright(브라우저) 없이 사용자의 실제 쿠키를 이용해 
    인스타그램 내부 API에서 직접 데이터를 추출합니다.
    """
    result = {
        "post_url": post_url,
        "caption": "",
        "image_urls": [],
        "post_type": "image",
        "error": None
    }

    try:
        # 1. URL 정리 (불필요한 파라미터 제거 후 API 호출용 파라미터 추가)
        parsed = urlparse(post_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if not clean_url.endswith('/'):
            clean_url += '/'
            
        # 💡 핵심: 인스타그램에게 HTML 화면 대신 JSON 데이터를 달라고 요청하는 파라미터
        api_url = f"{clean_url}?__a=1&__d=dis"

        # 2. 헤더 및 사용자 쿠키 세팅
        headers = {
            # 모바일 앱에서 접속한 것처럼 위장 (아이폰 User-Agent)
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Cookie": f"sessionid={session_id}"
        }

        # 3. 데이터 요청 (requests 사용, 브라우저 로딩이 없어 매우 빠름)
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            result["error"] = f"접근 실패 (상태 코드: {response.status_code}). 쿠키 만료 또는 비공개 계정일 수 있습니다."
            return result

        # 4. JSON 데이터 파싱 (HTML 태그를 찾을 필요가 없음!)
        data = response.json()
        
        # 인스타그램 API 구조 파악
        items = data.get("items", [])
        if not items:
            result["error"] = "게시물 데이터를 찾을 수 없습니다."
            return result
            
        post_data = items[0]

        # 📝 본문(Caption) 추출
        caption_dict = post_data.get("caption")
        if caption_dict:
            result["caption"] = caption_dict.get("text", "")

        # 📸 미디어(이미지/비디오) 추출
        if "carousel_media" in post_data:
            # 다중 이미지(Carousel)인 경우
            result["post_type"] = "carousel"
            for media in post_data["carousel_media"]:
                # 여러 화질 중 가장 고화질(첫 번째 candidate) 선택
                candidates = media.get("image_versions2", {}).get("candidates", [])
                if candidates:
                    result["image_urls"].append(candidates[0]["url"])
                    
        elif "image_versions2" in post_data:
            # 단일 이미지인 경우
            candidates = post_data["image_versions2"].get("candidates", [])
            if candidates:
                result["image_urls"].append(candidates[0]["url"])
                
            # 비디오 여부 체크
            if "video_versions" in post_data:
                result["post_type"] = "video"

    except Exception as e:
        result["error"] = f"API 크롤링 중 예외 발생: {str(e)}"

    return result

# --- 테스트 실행부 ---
if __name__ == "__main__":
    # 🔥 테스트할 URL과 사용자 쿠키 입력
    TEST_URL = "https://www.instagram.com/p/DNSF5jryTof/"
    SESSION_ID = "66800932735%3AkVPzTn1cdOCvwk%3A21%3AAYifS7X9eYVuTGD36Dxeoihm_bnJu2Npi8xzz1MIUw" 
    
    print("🚀 API 통신 기반 초경량 크롤링 시작...")
    api_result = extract_instagram_data_via_api(TEST_URL, SESSION_ID)
    
    print("\n✅ 크롤링 결과:")
    print(json.dumps(api_result, indent=4, ensure_ascii=False))