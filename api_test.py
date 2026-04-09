import asyncio
import httpx
import urllib.parse
import json

async def fetch_musinsa_direct(query: str, size: int) -> list:
    # 1. 쿼리 완벽하게 URL 인코딩 ("숏패딩" -> "%EC%88%8F%ED%8C%A8%EB%94%A9")
    encoded_query = urllib.parse.quote(query)
    
    # 2.httpx의 params 파라미터를 쓰지 않고, 브라우저가 쏘는 그대로 URL을 수제 조립
    # 빈 값(testGroup=, seenAds=)과 caller=SEARCH 등을 하나도 빠짐없이 넣어야 함.
    raw_url = (
        f"https://api.musinsa.com/api2/dp/v2/plp/goods"
        f"?gf=A"
        f"&keyword={encoded_query}"
        f"&sortCode=POPULAR"
        f"&isUsed=false"
        f"&page=1"
        f"&size={size}"
        f"&testGroup="
        f"&seen=0"
        f"&seenAds="
        f"&caller=SEARCH"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.musinsa.com",
        "Referer": f"https://www.musinsa.com/search/musinsa/integration?q={encoded_query}",
        # 가끔 필요한 추가 위장 헤더
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
    }

    # 3. HTTP/2 활성화 (가끔 최신 CDN들은 HTTP/1.1 봇을 400으로 튕겨냄)
    async with httpx.AsyncClient(http2=True) as client:
        try:
            # params를 빼고 raw_url을 그대로 던짐!
            response = await client.get(raw_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            
            items = response.json().get("data", {}).get("list", [])
            results = []
            
            for item in items:
                if item.get("isSoldOut") == True:
                    continue
                    
                results.append({
                    "shop": "MUSINSA",
                    "title": item.get("goodsName", "상품명 없음"),
                    "brand": item.get("brandName", "브랜드 미상"),
                    "price": f"{item.get('price', 0):,}원",
                    "sale_rate": f"{item.get('saleRate', 0)}%" if item.get('saleRate') else "0%",
                    "image_url": item.get("thumbnail", ""),
                    "url": item.get("goodsLinkUrl", "")
                })
                
            return results
            
        except Exception as e:
            print(f"무신사 다이렉트 검색 실패 ({query}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 코드: {e.response.status_code}")
                print(f"응답 본문: {e.response.text}") # 400 에러일 때 서버가 뱉는 진짜 이유가 여기 찍힘
            return []

# 테스트 코드
async def run_test():
    test_queries = ["숏패딩", "오버핏 스트릿 후드티"]
    for q in test_queries:
        print(f"\n검색어: '{q}' API 찌르는 중...")
        results = await fetch_musinsa_direct(q, size=100)
        if results:
            print(f"추출 성공! (총 {len(results)}개)")
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("결과를 가져오지 못했습니다.")

if __name__ == "__main__":
    asyncio.run(run_test())