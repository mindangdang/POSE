import httpx
import uuid
from typing import Optional

domain_map = {
        "musinsa.com": "무신사",
        "m.bunjang.co.kr" : "번개장터",
        "fruitsfamily.com": "후루츠패밀리",
        "zara.com": "자라",
        "instagram.com": "인스타그램"
    }

async def fetch_from_single_site(
    client: httpx.AsyncClient, 
    query: str, 
    domain: str, 
    site_name: str, 
    current_page: int, 
    serp_api_key: str, 
    params: Optional[dict] = None
) -> list[dict]:
    if params is None:
        params = {
            "engine": "google_images",
            "q": query,
            "api_key": serp_api_key,
            "ijn": (current_page - 1) // 3, # 100개 단위 배칭 (UI 1~3p -> ijn 0, 4~6p -> ijn 1)
            "gl": "kr",
            "hl": "ko"
        }

    try:
        print(f"[{site_name or 'SerpApi'}] API 요청 파라미터: q='{query}', ijn={params.get('ijn')}")
        response = await client.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        data = response.json()
        
        # Google Images는 'images_results', Google Lens는 'visual_matches'를 사용함
        items = data.get("images_results") or data.get("visual_matches") or []
        print(f"[{site_name or 'SerpApi'}] 검색 성공: {len(items)}개")
        
        results = []
        for item in items:
            # 이미지 URL 추출 로직 통합
            image_url = item.get("thumbnail", "")
            if "original" in item and "instagram" not in domain:
                image_url = item.get("original") or image_url
            
            # 가격 정보 추출 (Lens는 dict 형태일 수 있음)
            price = item.get("price")
            if isinstance(price, dict):
                price = price.get("value")
            price = price or item.get("snippet") or "가격 미상"
            
            shop = item.get("source") or site_name or "알 수 없는 샵"

            results.append({
                "id": str(uuid.uuid4()),
                "category": "PRODUCT",
                "sub_category": query if not query.startswith("http") else "PRODUCT",
                "recommend": f"{shop}에서 발견한 아이템",
                "image_url": image_url,
                "url": item.get("link", ""),
                "facts": {
                    "title": item.get("title", "상품명 없음"),
                    "Price": price,
                    "Shop": shop,
                },
            })
        return results

    except Exception as e:
        print(f"[{domain}] 검색 실패: {e}")
        return []