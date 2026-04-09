import asyncio
import httpx
import json

async def fetch_fruitsfamily_direct(query_keyword: str, limit: int = 40) -> list:
    print(f"\n🔍 후루츠패밀리: '{query_keyword}' 실시간 디깅 중...")
    
    url = "https://web-server.production.fruitsfamily.com/graphql"
    
    # 1. 민준이가 완벽하게 발라낸 GraphQL 쿼리 원본 (Fragment 포함)
    graphql_query = """
    query SeeProducts($filter: ProductFilter!, $offset: Int, $limit: Int, $sort: String) {
      searchProducts(filter: $filter, offset: $offset, limit: $limit, sort: $sort) {
        ...ProductFragment
        ...ProductDetailsPreloadFragment
        price
        __typename
      }
    }

    fragment ProductFragment on ProductNotMine {
      id
      title
      brand
      status
      external_url
      resizedSmallImages
      __typename
    }

    fragment ProductDetailsPreloadFragment on ProductNotMine {
      id
      createdAt
      category
      title
      description
      brand
      price
      status
      external_url
      resizedSmallImages
      is_visible
      size
      condition
      discount_rate
      like_count
      __typename
    }
    """
    
    # 2. 변수 셋업 (네가 훔쳐온 variables 구조 그대로!)
    variables = {
        "filter": {"query": query_keyword},
        "sort": "POPULAR",
        "offset": 0,
        "limit": limit
    }

    # 3. 최종 페이로드 조립
    payload = {
        "operationName": "SeeProducts",
        "query": graphql_query,
        "variables": variables
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://fruitsfamily.com",
        "Referer": "https://fruitsfamily.com/",
    }

    async with httpx.AsyncClient(http2=True) as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            
            response_data = response.json()
            
            # GraphQL은 보통 데이터가 data 안에 깊숙이 들어있어!
            items = response_data.get("data", {}).get("searchProducts", [])
            results = []
            
            for item in items:
                # ⭐️ 무신사의 isSoldOut 같은 역할! status가 AVAILABLE인 것만 가져오기 (품절컷)
                if item.get("status") != "selling":
                    continue
                
                # 이미지 배열에서 첫 번째 사진 추출
                images = item.get("resizedSmallImages", [])
                image_url = images[0] if images else ""
                
                results.append({
                    "shop": "FRUITSFAMILY",
                    "title": item.get("title", "상품명 없음"),
                    "brand": item.get("brand", "브랜드 미상"),
                    "price": f"{item.get('price', 0):,}원",
                    "image_url": image_url,
                    # 후루츠패밀리 상품 링크는 보통 /product/{id} 형태!
                    "url": f"https://fruitsfamily.com/product/{item.get('id', '')}",
                    # 중고 상태나 좋아요 수도 원한다면 뺄 수 있음!
                    "condition": item.get("condition", ""),
                    "like_count": item.get("like_count", 0)
                })
                
            return results
            
        except Exception as e:
            print(f"🚨 후루츠패밀리 API 에러 ({query_keyword}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 본문: {e.response.text}")
            return []

# 테스트 실행
async def run_test():
    test_query = "빈티지 데님"
    results = await fetch_fruitsfamily_direct(test_query, limit=10) # 테스트니까 10개만!
    
    if results:
        print(f"✅ 추출 성공! (총 {len(results)}개)")
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("❌ 결과를 가져오지 못했습니다.")

if __name__ == "__main__":
    asyncio.run(run_test())