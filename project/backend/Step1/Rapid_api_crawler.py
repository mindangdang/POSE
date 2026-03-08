import requests
import json
import re
import os

def Rapid_crawler(post_url: str) -> dict:
    # 1️⃣ URL에서 짧은 고유 코드(Shortcode) 추출 
    # 예: https://www.instagram.com/p/DThhqQAjxcW/ -> DThhqQAjxcW
    try:
        shortcode = post_url.split("/p/")[1].split("/")[0]
    except IndexError:
        return {"error": "유효하지 않은 인스타그램 게시물 URL입니다."}

    # 2️⃣ RapidAPI 엔드포인트 및 설정
    # (주의: 사용하시는 특정 API에 따라 url과 파라미터 이름은 다를 수 있습니다)
    url = "https://instagram-scraper-api2.p.rapidapi.com/v1/post_info"
    querystring = {"code_or_id_or_url": shortcode}

    # 🔑 발급받은 API 키를 넣으세요! (실전에서는 os.environ.get("RAPIDAPI_KEY") 권장)
    headers = {
        "X-RapidAPI-Key": "여기에_발급받은_RapidAPI_키를_입력하세요",
        "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
    }

    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "error": None,
    }

    try:
        print(f"🌐 [API 호출] [{shortcode}] 게시물 데이터를 요청합니다...")
        
        # 브라우저 띄울 필요 없이 GET 요청 한 방으로 끝!
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        response.raise_for_status()
        data = response.json()

        # 3️⃣ 응답 데이터 파싱 (API가 주는 JSON 구조에 맞게 매핑)
        post_data = data.get("data", {})
        
        if not post_data:
            result["error"] = "게시물 데이터를 찾을 수 없습니다. (삭제되었거나 비공개 계정)"
            return result

        # 본문(Caption) 추출
        result["caption"] = post_data.get("caption", {}).get("text", "")
        
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

    except Exception as e:
        result["error"] = f"API 호출 중 에러 발생: {str(e)}"

    return result


# --- 실행 테스트 ---
if __name__ == "__main__":
    test_url = "https://www.instagram.com/p/DThhqQAjxcW/"
    
    api_result = Rapid_crawler(test_url)
    
    if api_result.get("error"):
        print(f"❌ 에러: {api_result['error']}")
    else:
        print("✅ API 수집 성공!")
        print(f"📝 본문: {api_result['caption'][:30]}...")
        print(f"🏷️ 해시태그: {api_result['hashtags']}")
        print(f"🖼️ 이미지 개수: {len(api_result['image_urls'])}장")