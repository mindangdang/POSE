import urllib.parse

def generate_review_links(product_name: str) -> dict:
    """상품명을 받아 주요 쇼핑 플랫폼의 검색/리뷰 링크를 반환합니다."""
    
    # URL에 들어갈 수 있도록 한글/특수문자 인코딩 (예: "나이키 에어포스" -> "%EB%82%98...")
    encoded_name = urllib.parse.quote(product_name)
    
    links = {
        # 네이버 쇼핑 (한국 리뷰의 최고봉)
        "naver_shopping": f"https://search.shopping.naver.com/search/all?query={encoded_name}",
        
        # 구글 쇼핑 (글로벌/범용)
        "google_shopping": f"https://www.google.com/search?tbm=shop&q={encoded_name}",
        
        # 무신사 (패션 특화 앱이니까 필요하다면)
        "musinsa": f"https://www.musinsa.com/search/musinsa/integration?q={encoded_name}"
    }
    
    return links

# 테스트
# print(generate_review_links("아르떼미데 톨로메오 조명"))