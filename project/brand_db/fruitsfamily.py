import requests

url = "https://web-server.production.fruitsfamily.com/graphql"

headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

def search_popular_brands():
    payload = {
        "operationName": "getPopularKeywordsByFilterCached",
        "variables": {},
        "query": """
        query getPopularKeywordsByFilterCached {
            getPopularKeywordsByFilterCached {
                popularBrands {
                    name
                }
            }
        }
        """
    }

    res = requests.post(url, json=payload, headers=headers)
    return res.json()

def search_brand(brand_name):
    payload = {
        "operationName": "getBrandByNameResponse",
        "variables": {
            "name": brand_name
        },
        "query": """
        query getBrandByNameResponse($name: String!) {
            getBrandByNameResponse(name: $name) {
                code
                brand {
                    id
                    name
                    name_kr
                    description
                    follow_count
                    product_count
                    __typename
                }
                __typename
            }
        }
        """
    }

    res = requests.post(url, json=payload, headers=headers)
    data = res.json()
    
    brand_data = data.get("data", {}).get("getBrandByNameResponse", {})
    if brand_data.get("code") == 200 and brand_data.get("brand"):
        return brand_data["brand"]["id"]
    return None


def get_similar(brand_id):
    payload = {
        "operationName": "getSimilarBrands",
        "variables": {
            "brand_id": brand_id
        },
        "query": """
        query getSimilarBrands($brand_id: Int!) {
            getSimilarBrands(brand_id: $brand_id) {
                id
                name
                name_kr
                follow_count
                __typename
            }
        }
        """
    }

    res = requests.post(url, json=payload, headers=headers)
    data = res.json()
    return data.get("data", {}).get("getSimilarBrands", [])

if __name__ == "__main__":
    brand_id = search_brand("Vivienne Westwood")
    if brand_id:
        print(f"검색된 브랜드 ID: {brand_id}")
        similar_brands = get_similar(int(brand_id))
        
        print(f"\n총 {len(similar_brands)}개의 유사 브랜드를 찾았습니다:")
        for brand in similar_brands:
            print(f"- {brand.get('name')} ({brand.get('name_kr')}): 팔로워 {brand.get('follow_count')}명")
    else:
        print("브랜드를 찾을 수 없습니다.")