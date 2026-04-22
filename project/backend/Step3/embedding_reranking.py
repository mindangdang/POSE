import os
import torch
import torch.nn.functional as F
import numpy as np
import gc
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# 멀티스레딩 억제로 CPU/RAM 스파이크 방지
os.environ["OMP_NUM_THREADS"] = "1"

class FashionReRankingPipelineLight:
    def __init__(self, lambda_weight=0.6):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lambda_weight = lambda_weight
        
        print("🔄 Fashion-CLIP 모델 로드 중 (단일 모델 적재)...")
        self.model_id = "patrickjohncyh/fashion-clip"
        self.processor = CLIPProcessor.from_pretrained(self.model_id)
        self.model = CLIPModel.from_pretrained(self.model_id).to(self.device)
        self.model.eval()
        
        print(f"✅ 시스템 초기화 완료. (동작 환경: {self.device})")

    def preprocess_image(self, image_path: str) -> Image:
        """배경 제거 없이 이미지 포맷만 RGB로 일관되게 정규화합니다."""
        # 투명 배경(RGBA)이 있을 경우 흰색으로 채운 뒤 RGB로 변환하여 에러 방지
        img = Image.open(image_path).convert("RGBA")
        white_canvas = Image.new("RGBA", img.size, "WHITE")
        white_canvas.paste(img, (0, 0), img)
        return white_canvas.convert("RGB")

    @torch.no_grad()
    def get_pure_vibe_vector(self, image_path: str, category_text: str) -> torch.Tensor:
        """이미지 임베딩에서 카테고리 텍스트 임베딩을 차감하여 순수 무드 추출"""
        clean_img = self.preprocess_image(image_path)
        
        # 텍스트/이미지 통합 인코딩
        inputs = self.processor(
            text=[category_text], 
            images=clean_img, 
            return_tensors="pt", 
            padding=True
        ).to(self.device)
        
        outputs = self.model(**inputs)
        text_features = outputs.text_embeds
        img_features = outputs.image_embeds
        
        # 잔차 벡터 및 정규화
        vibe_vector = img_features - (self.lambda_weight * text_features)
        return F.normalize(vibe_vector, p=2, dim=1)

    @torch.no_grad()
    def build_user_taste_vector(self, wishlist_items: list[dict]) -> torch.Tensor:
        """위시리스트 배열에서 SVD(PCA)를 통해 지배적인 미학 축(Taste Vector) 추출"""
        print("🧠 위시리스트 취향 벡터 합성(PCA) 중...")
        vibe_vectors = []
        for item in wishlist_items:
            vec = self.get_pure_vibe_vector(item["image_path"], item["category"])
            vibe_vectors.append(vec)
            
        wishlist_tensor = torch.cat(vibe_vectors, dim=0)
        
        if wishlist_tensor.size(0) == 1:
            return wishlist_tensor
            
        # SVD 연산
        mean_vec = torch.mean(wishlist_tensor, dim=0, keepdim=True)
        centered_vectors = wishlist_tensor - mean_vec
        U, S, Vh = torch.linalg.svd(centered_vectors, full_matrices=False)
        first_pc = Vh[0, :].unsqueeze(0)
        
        taste_vector = mean_vec + (0.5 * first_pc)
        return F.normalize(taste_vector, p=2, dim=1)

    def calculate_cosine_similarity(self, vec1: torch.Tensor, vec2: torch.Tensor) -> float:
        return F.cosine_similarity(vec1, vec2, dim=1).item()

    def rerank_search_results(self, search_results: list[dict], user_taste_vector: torch.Tensor) -> list[dict]:
        """추출된 취향 벡터와 매물 간의 유사도 정렬 (메모리 세이프 모드)"""
        print(f"🔍 {len(search_results)}개 상품 리랭킹 연산 시작...")
        
        for item in search_results:
            try:
                item_vibe_vector = self.get_pure_vibe_vector(item["image_path"], item["category"])
                score = self.calculate_cosine_similarity(user_taste_vector, item_vibe_vector)
                item["aesthetic_score"] = round(score, 4)
                
                # 메모리 플러싱
                del item_vibe_vector
                
            except Exception as e:
                print(f"⚠️ {item.get('title', 'Unknown')} 처리 에러: {e}")
                item["aesthetic_score"] = -1.0
            
            finally:
                gc.collect() # 루프마다 가비지 컬렉터 강제 호출
                
        return sorted(search_results, key=lambda x: x["aesthetic_score"], reverse=True)
# =====================================================================
# 테스트 실행
# =====================================================================
if __name__ == "__main__":
    pipeline = FashionReRankingPipelineLight(lambda_weight=0.6)
    
    # User Tower 데이터
    wishlist_data = [
        {"image_path": "project/backend/insta_vibes/3d937f3be8ba4fa2925ca0bd631e1b57.jpg", "category": "jacket"},
        {"image_path": "project/backend/insta_vibes/9a7aafdeb8e348a89473ab838075ccb2.jpg", "category": "Tshirt"},
        {"image_path": "project/backend/insta_vibes/24f2556a1f7649d2a7bae5499f7d87dd.jpg", "category": "sneakers"}
    ]
    
    taste_vector = pipeline.build_user_taste_vector(wishlist_data)
    
    search_results_data = [
        {"title": "이상한 셔츠", "image_path": "project/backend/insta_vibes/36bdf0172c9141fdacac16c8c2497e91.jpg", "category": "shirt"},
        {"title": "예쁜 신발", "image_path": "project/backend/insta_vibes/33f4c91a495246b7abbedfdc36b8534a.jpg", "category": "sneakers"},
        {"title": "이상한 후집", "image_path": "project/backend/insta_vibes/51d39b838bf14486bbda7c9ccabbb3f1.jpg", "category": "hood zipup"},
        {"title": "예쁜 바지", "image_path": "project/backend/insta_vibes/acf076b749c642258d18e1f5ab2de17a.jpg", "category": "pants"}
    ]
    
    final_ranked_items = pipeline.rerank_search_results(search_results_data, taste_vector)
    
    print("\n[최종 PCA 기반 리랭킹 결과]")
    for rank, item in enumerate(final_ranked_items, 1):
        print(f"{rank}위 | {item['aesthetic_score']} | {item['title']}")