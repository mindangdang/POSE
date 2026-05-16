import asyncio
import io
import httpx
from PIL import Image

# GPU 서버의 파이프라인 클래스 임포트
from embedding_reranking import FashionSiglipReRankingPipeline


async def load_image_from_url(url: str) -> Image.Image:
    """URL에서 이미지를 비동기로 다운로드하여 PIL Image 객체로 반환합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15.0, follow_redirects=True)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")


async def run_test():
    # =====================================================================
    # 1. 테스트 데이터 뼈대 준비 (실제 데이터로 변경하여 사용하세요)
    # =====================================================================
    user_query = "denim pants"  
    
    # [image_url, category] 형태의 위시리스트 데이터
    wishlist_images = [
        # ["https://...", "PRODUCT"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20251022/5630579/5630579_17611237045254_big.jpg?w=1200", "sunglasses"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20260121/5920411/5920411_17708906074908_big.jpg?w=1200", "zip hoodie"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20251119/5753503/5753503_17635382548509_big.jpg?w=1200", "ring"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20240924/4458399/4458399_17273479266052_big.jpg?w=1200", "jeans"],
        ["https://image.production.fruitsfamily.com/public/product/resized%40width620/R6r-GfEGB-56C7EBAF-5A31-4C98-91EB-53E17867F435.jpg", "blazer"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20250701/5216530/5216530_17548721425024_big.jpg?w=1200", "sneakers"],
        ["https://image.msscdn.net/thumbnails/images/prd_img/20260113/5891000/detail_5891000_17709656327469_big.jpg?w=1200", "zip hoodie"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20260206/5993219/5993219_17706970502433_big.jpg?w=1200", "tote bag"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20251106/5695421/5695421_17682091451363_big.png?w=1200", "loafers"]
    ]
    
    # {'item_name': [image_url, sub_category]} 형태의 테스트할 이미지 데이터
    test_images = {
        # "아이템 이름": ["https://...", "JACKET"],
        "밤티1" : ["https://image.msscdn.net/thumbnails/images/goods_img/20250107/4702958/4702958_17754496380398_big.jpg?w=1200", "jeans"],
        "밤티2(여자꺼)" : ["https://image.msscdn.net/thumbnails/images/goods_img/20260330/6218794/6218794_17749298495116_big.jpg?w=1200", "jeans"],
        "밤티3" : ["https://image.msscdn.net/thumbnails/images/prd_img/20251203/5802532/detail_5802532_17647660268008_big.jpg?w=1200", "jeans"],
        "밤티4" : ["https://image.msscdn.net/thumbnails/images/prd_img/20260224/6048622/detail_6048622_17732790227548_big.jpg?w=1200", "jeans"],
        "내 취향1" : ["https://image.msscdn.net/thumbnails/images/prd_img/20250818/5331560/detail_5331560_17579013091105_big.jpg?w=1200", "jeans"],
        "내 취향2" : ["https://image.msscdn.net/thumbnails/images/goods_img/20250304/4852252/4852252_17527701383488_big.jpg?w=1200", "jeans"],
        "내 취향3" : ["https://image.msscdn.net/thumbnails/images/goods_img/20260330/6219956/6219956_17748518187354_big.jpg?w=1200", "jeans"],
        "강아지 사진" : ["https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS7g0bXrNGNd0WWuLmJIzfjA4Le5KHs_LKwpw&s", "dog"],
        "인스타 자켓 썸네일" : ["https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ98paK0v9rproAjw2Vxw0pBZ4pkdOsKSyWTg&s", 'jacket'],
        "나폴레옹" : ["https://nanostudio-official.com/cdn/shop/files/result-_2026-04-2218.54.46.jpg?v=1776965446&width=1080", "jacket"]
    }

    # =====================================================================
    # 2. 파이프라인 초기화 및 벡터 생성
    # =====================================================================
    pipeline = FashionSiglipReRankingPipeline()

    print(f"\n[Query] '{user_query}' 인코딩 중...")
    query_vector = pipeline.encode_text(user_query)
    
    print("\n[Wishlist] 이미지 벡터 추출 및 취향 벡터 합성 중...")
    wishlist_vectors = []
    for img_url, category in wishlist_images:
        try:
            img_obj = await load_image_from_url(img_url)
            vec = pipeline.get_image_vector(img_obj, category)
            wishlist_vectors.append(vec)
        except Exception as e:
            print(f"위시리스트 이미지 로드 실패 ({img_url}): {e}")
            
    if not wishlist_vectors:
        print("유효한 위시리스트 벡터가 없어 테스트를 종료합니다.")
        return

    user_taste_profile = pipeline.build_user_taste_vector(wishlist_vectors)
    
    # =====================================================================
    # 3. 테스트 이미지 평가 (단일 아이템)
    # =====================================================================
    print("\n[Test] 테스트 이미지들에 대해 코사인 유사도 평가 진행 중...")
    evaluated_items = []
    for item_name, (img_url, sub_category) in test_images.items():
        try:
            img_obj = await load_image_from_url(img_url)
            item = {
                "image_url": img_url,
                "sub_category": sub_category,
                "item_name": item_name,
                "image_obj": img_obj  # 파이프라인 내부에서 pop하여 사용됨
            }
            
            result = pipeline.evaluate_single_item(
                item=item,
                user_taste_profile=user_taste_profile,
                query_vector=query_vector,
                alpha=0.4
            )
            
            if result:
                evaluated_items.append(result)
        except Exception as e:
            print(f"테스트 이미지 평가 실패 ({img_url}): {e}")
        

    # =====================================================================
    # 4. 결과 정렬 및 출력
    # =====================================================================
    # (1) Semantic Score 기준 내림차순 (쿼리 일치도)
    semantic_sorted = sorted(evaluated_items, key=lambda x: x.get("semantic_score", 0.0), reverse=True)
    print("\n=== [Semantic Score (쿼리 일치도) 기준 정렬] ===")
    for item in semantic_sorted:
        print(f"Semantic: {item['semantic_score']:.4f} | Aesthetic: {item['aesthetic_score']:.4f} (C: {item['consensus_score']:.4f}, P: {item['prototype_score']:.4f}) | Item: {item['item_name']} | URL: {item['image_url']}")
        
    # (2) Aesthetic Score 기준 내림차순 (취향 일치도)
    aesthetic_sorted = sorted(evaluated_items, key=lambda x: x.get("aesthetic_score", 0.0), reverse=True)
    print("\n=== [Aesthetic Score (취향 일치도) 기준 정렬] ===")
    for item in aesthetic_sorted:
        print(f"Aesthetic: {item['aesthetic_score']:.4f} (C: {item['consensus_score']:.4f}, P: {item['prototype_score']:.4f}) | Semantic: {item['semantic_score']:.4f} | Item: {item['item_name']} | URL: {item['image_url']}")


if __name__ == "__main__":
    asyncio.run(run_test())
