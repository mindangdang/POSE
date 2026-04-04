import httpx
import re
import os
import logging

logger = logging.getLogger(__name__)

# URL에서 shortcode를 안전하게 추출하는 정규식 (p 또는 reel 모두 지원, 쿼리 파라미터 무시)
SHORTCODE_PATTERN = re.compile(r"/(?:p|reel)/([^/?#&]+)")

# [최적화] async def로 변경하여 비동기 호출 지원
async def Rapid_crawler(post_url: str) -> dict:
    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "error": None,
    }

    # 1. 안전한 Shortcode 추출
    match = SHORTCODE_PATTERN.search(post_url)
    if not match:
        result["error"] = "유효하지 않은 인스타그램 게시물 URL입니다. (/p/ 또는 /reel/ 형식이 필요합니다)"
        return result
    
    shortcode = match.group(1)

    # 2. 환경변수에서 API 키 강제 가져오기 (보안)
    rapidapi_key = os.environ.get("RAPIDAPI_KEY")
    if not rapidapi_key:
        result["error"] = "서버에 RAPIDAPI_KEY 환경변수가 설정되지 않았습니다."
        return result

    url = "https://instagram-scraper-api2.p.rapidapi.com/v1/post_info"
    querystring = {"code_or_id_or_url": shortcode}

    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
    }

    try:
        print(f"[API 호출] [{shortcode}] 비동기 데이터 요청 중...")
        
        # 3. 비동기 HTTP 통신 (서버 병목 해결)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=querystring, timeout=15.0)
            response.raise_for_status()
            data = response.json()

        # 응답 데이터 파싱
        post_data = data.get("data", {})
        
        if not post_data:
            result["error"] = "게시물 데이터를 찾을 수 없습니다. (삭제되었거나 비공개 계정)"
            return result

        # 본문(Caption) 추출 (안전한 타입 체크)
        caption_data = post_data.get("caption")
        if isinstance(caption_data, dict):
            result["caption"] = caption_data.get("text", "")
        elif isinstance(caption_data, str):
            result["caption"] = caption_data

        # 해시태그 추출 (본문에서 정규식으로 뽑아내기)
        if result["caption"]:
            result["hashtags"] = re.findall(r"(?<!\w)#([^\s#.,!?;:]+)", result["caption"])

        # 이미지 URL 추출 (여러 장인 Carousel과 1장짜리 분기 처리)
        if "carousel_media" in post_data:
            for item in post_data["carousel_media"]:
                # 가장 해상도가 높은 첫 번째 이미지 URL 가져오기
                candidates = item.get("image_versions2", {}).get("candidates", [])
                if candidates:
                    result["image_urls"].append(candidates[0].get("url"))
        else:
            candidates = post_data.get("image_versions2", {}).get("candidates", [])
            if candidates:
                result["image_urls"].append(candidates[0].get("url"))

    except httpx.HTTPStatusError as e:
        result["error"] = f"API HTTP 에러: {e.response.status_code} - 통신 실패"
    except Exception as e:
        result["error"] = f"API 호출 중 에러 발생: {str(e)}"

    return result

# --- 실행 테스트 (비동기에 맞게 수정) ---
if __name__ == "__main__":
    import asyncio
    from project.backend.config import load_backend_env
    
    load_backend_env()

    async def test():
        test_url = "https://www.instagram.com/p/DThhqQAjxcW/"
        api_result = await Rapid_crawler(test_url)
        
        if api_result.get("error"):
            print(f"에러: {api_result['error']}")
        else:
            print("API 수집 성공!")
            print(f"본문: {api_result['caption'][:30]}...")
            print(f"해시태그: {api_result['hashtags']}")
            print(f"이미지 개수: {len(api_result['image_urls'])}장")

    # 비동기 함수 실행
    asyncio.run(test())
