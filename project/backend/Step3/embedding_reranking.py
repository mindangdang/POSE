import os
import gc
import torch
import torch.nn.functional as F
from PIL import Image
import open_clip

# 멀티스레딩 억제로 CPU/RAM 스파이크 방지
os.environ["OMP_NUM_THREADS"] = "1"

class FashionSiglipReRankingPipeline:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FashionSiglipReRankingPipeline, cls).__new__(cls)
            cls._instance._is_initialized = False
        return cls._instance

    def __init__(self, lambda_weight=0.6):
        if self._is_initialized:
            self.lambda_weight = lambda_weight
            return
            
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lambda_weight = lambda_weight
        
        print("Marqo-FashionSigLIP 모델 로드 중 (In-Memory 모드)...")
        self.model_id = "hf-hub:Marqo/marqo-fashionSigLIP"
        
        # open_clip을 통한 모델, 전처리 모듈 및 토크나이저 로드
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(self.model_id)
        self.tokenizer = open_clip.get_tokenizer(self.model_id)
        
        if self.device == "cuda":
            self.model = self.model.to(torch.bfloat16)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        self._is_initialized = True
        print(f"시스템 초기화 완료. (동작 환경: {self.device})")

    def preprocess_image(self, img: Image.Image) -> Image.Image:
        """디스크 경로가 아닌, 메모리 상의 PIL 객체를 직접 받아 정규화합니다."""
        img = img.convert("RGBA")
        white_canvas = Image.new("RGBA", img.size, "WHITE")
        white_canvas.paste(img, (0, 0), img)
        return white_canvas.convert("RGB")

    @torch.no_grad()
    def build_user_taste_vector(self, wishlist_items: list[dict]) -> torch.Tensor:
        """위시리스트 배열에서 SVD(PCA)를 통해 지배적인 미학 축(Taste Vector) 추출"""
        print("위시리스트 취향 벡터 합성(PCA) 중...")
        vibe_vectors = []
        for item in wishlist_items:
            clean_img = self.preprocess_image(item["image_obj"])
            
            # 텍스트 & 이미지 인코딩
            image_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
            if self.device == "cuda":
                image_input = image_input.to(torch.bfloat16)
            text_input = self.tokenizer([item["category"]]).to(self.device)
            
            image_features = self.model.encode_image(image_input)
            text_features = self.model.encode_text(text_input)
            
            text_vec = F.normalize(text_features, p=2, dim=1)
            img_vec = F.normalize(image_features, p=2, dim=1)
            
            vibe_vector = img_vec - (self.lambda_weight * text_vec)
            vibe_vectors.append(F.normalize(vibe_vector, p=2, dim=1))
            
        wishlist_tensor = torch.cat(vibe_vectors, dim=0)
        
        if wishlist_tensor.size(0) == 1:
            return wishlist_tensor
            
        mean_vec = torch.mean(wishlist_tensor, dim=0, keepdim=True)
        centered_vectors = wishlist_tensor - mean_vec
        U, S, Vh = torch.linalg.svd(centered_vectors, full_matrices=False)
        first_pc = Vh[0, :].unsqueeze(0)
        
        taste_vector = mean_vec + (0.5 * first_pc)
        return F.normalize(taste_vector, p=2, dim=1)
    
    def encode_text(self, text: str) -> torch.Tensor:
        """쿼리 텍스트를 SigLIP 텍스트 임베딩으로 인코딩"""
        with torch.no_grad():
            text_input = self.tokenizer([text]).to(self.device)
            text_vector = F.normalize(self.model.encode_text(text_input), p=2, dim=1)
        return text_vector

    def calculate_cosine_similarity(self, vec1: torch.Tensor, vec2: torch.Tensor) -> float:
        return F.cosine_similarity(vec1, vec2, dim=1).item()

    @torch.no_grad()
    def rerank_search_results(
        self, 
        search_results: list[dict], 
        user_taste_vector: torch.Tensor, 
        query_text: str, 
        semantic_thresh: float = 0.10,
        aesthetic_thresh: float = 0.0
    ) -> list[dict]:
        """In-Memory 객체를 소비하며 Dual 필터링을 수행합니다. 배치 처리를 통해 속도 개선."""
        print(f"{len(search_results)}개 상품 2-Stage 필터링 및 리랭킹 시작...")
        
        # 1. 쿼리 벡터 추출 (Stage 1 필터링 용도)
        query_vector = self.encode_text(query_text)
        
        valid_results = []
        
        # 배치 처리를 위한 리스트 준비
        images = []
        categories = []
        indices = []
        
        for idx, item in enumerate(search_results):
            try:
                # 메모리에서 이미지 객체를 꺼내고 딕셔너리에서 연결을 끊음 (RAM 확보)
                raw_img = item.pop("image_obj") 
                clean_img = self.preprocess_image(raw_img)
                images.append(clean_img)
                categories.append(item["category"])
                indices.append(idx)
            except Exception as e:
                print(f"{item.get('title', 'Unknown')} 전처리 에러: {e}")
        
        if not images:
            return []
        
        # 배치로 이미지 벡터 추출
        img_inputs = torch.stack([self.preprocess(img) for img in images]).to(self.device)
        if self.device == "cuda":
            img_inputs = img_inputs.to(torch.bfloat16)
        raw_img_vectors = F.normalize(self.model.encode_image(img_inputs), p=2, dim=1)
        
        # 배치로 카테고리 벡터 추출
        cat_inputs = self.tokenizer(categories).to(self.device)
        cat_vectors = F.normalize(self.model.encode_text(cat_inputs), p=2, dim=1)
        
        for i, idx in enumerate(indices):
            item = search_results[idx]
            raw_img_vector = raw_img_vectors[i].unsqueeze(0)
            cat_vector = cat_vectors[i].unsqueeze(0)
            
            # ==========================================================
            # [Stage 1] Semantic 필터링 (쿼리 벡터 vs 원본 이미지 벡터)
            # ==========================================================
            semantic_score = self.calculate_cosine_similarity(query_vector, raw_img_vector)
            
            if semantic_score < semantic_thresh:
                print(f"  [의미 탈락] {item.get('title')} (Score: {semantic_score:.4f})")
                continue
            
            # ==========================================================
            # [Stage 2] Aesthetic 필터링 (취향 벡터 vs 잔차 벡터)
            # ==========================================================
            vibe_vector = raw_img_vector - (self.lambda_weight * cat_vector)
            pure_vibe_vector = F.normalize(vibe_vector, p=2, dim=1)
            
            aesthetic_score = self.calculate_cosine_similarity(user_taste_vector, pure_vibe_vector)
            
            if aesthetic_score < aesthetic_thresh:
                print(f"[취향 탈락] {item.get('title')} (Score: {aesthetic_score:.4f})")
                continue
                
            # 두 스테이지를 모두 통과한 생존 데이터 기록
            item["semantic_score"] = round(semantic_score, 4)
            item["aesthetic_score"] = round(aesthetic_score, 4)
            valid_results.append(item)
        
        # 메모리 정리
        for img in images:
            img.close()
        gc.collect()
                
        return sorted(valid_results, key=lambda x: x["aesthetic_score"], reverse=True)
