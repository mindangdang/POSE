import os
from project.backend.app.core.settings import load_backend_env
from apify_client import ApifyClient

load_backend_env()
api_key = os.environ.get("APIFY_API_KEY") 
client = ApifyClient(api_key)

def apify_insta_crawler(post_url: str, result_nums: int):
    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "post_type": "image",
        "error": None,
        "blocked": False,
        "requires_login": False,
    }

    try:
        run_input = {
            "directUrls": [post_url],
            "resultsLimit": result_nums,
        }

        print(f"Apify 스크래핑 작업을 요청합니다: {post_url}")
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)

        dataset_id = run["defaultDatasetId"]
        items = list(client.dataset(dataset_id).iterate_items())
        
        if not items:
            result["error"] = "검색된 결과가 없습니다."
            return result

        item = items[0]
        result["caption"] = item.get("caption", "")
        result["hashtags"] = item.get("hashtags", [])
        
        # 이미지 URL 추출 (Carousel 대응)
        images = item.get("images", [])
        if images:
            result["image_urls"] = [img.get("url") for img in images if img.get("url")]
        elif item.get("displayUrl"):
            result["image_urls"] = [item.get("displayUrl")]
        
        # 게시물 타입 매핑
        item_type = item.get("type", "").lower()
        if item_type == "video": result["post_type"] = "video"
        elif item_type == "sidecar" or len(result["image_urls"]) > 1: result["post_type"] = "carousel"
        
        return result
    except Exception as e:
        print(f"Apify 작업 중 에러 발생: {e}")
        result["error"] = str(e)
        return result