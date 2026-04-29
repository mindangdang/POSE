import concurrent.futures
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
    def get_image_vector(self, img: Image.Image, category: str) -> list[float]:
        """단일 이미지와 카테고리를 받아 Vibe Vector를 반환합니다. (DB 저장용)"""
        clean_img = self.preprocess_image(img)
        
        image_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
        if self.device == "cuda":
            image_input = image_input.to(torch.bfloat16)
        text_input = self.tokenizer([category]).to(self.device)
        
        image_features = self.model.encode_image(image_input)
        text_features = self.model.encode_text(text_input)
        
        text_vec = F.normalize(text_features, p=2, dim=1)
        img_vec = F.normalize(image_features, p=2, dim=1)
        
        image_vector = img_vec - (self.lambda_weight * text_vec)
        image_vector = F.normalize(image_vector, p=2, dim=1)
        
        return image_vector[0].tolist()

    @torch.no_grad()
    def build_user_taste_vector(self, image_vectors: list[list[float]]) -> torch.Tensor:
        """사전 추출된 위시리스트 벡터 배열에서 SVD(PCA)를 통해 지배적인 미학 축(Taste Vector) 추출"""
        print("위시리스트 취향 벡터 합성(PCA) 중...")
        if not image_vectors:
            return None
            
        wishlist_tensor = torch.tensor(image_vectors, device=self.device)
        if self.device == "cuda":
            wishlist_tensor = wishlist_tensor.to(torch.bfloat16)
        
        if wishlist_tensor.size(0) == 1:
            return wishlist_tensor
            
        mean_vec = torch.mean(wishlist_tensor, dim=0, keepdim=True)
        centered_vectors = wishlist_tensor - mean_vec
        
        U, S, Vh = torch.linalg.svd(centered_vectors.to(torch.float32), full_matrices=False)
        first_pc = Vh[0, :].unsqueeze(0).to(self.device)
        
        if self.device == "cuda":
            first_pc = first_pc.to(torch.bfloat16)
        
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
        if not search_results:
            return []
            
        print(f"{len(search_results)}개 상품 2-Stage 필터링 및 리랭킹 시작...")
        
        # 1. 쿼리 벡터 추출 (Stage 1 필터링 용도)
        query_vector = self.encode_text(query_text)
        
        # 배치 처리를 위한 리스트 준비
        images = []
        categories = []
        items_with_images = [] # 전처리 성공한 아이템만 저장
        
        def _process_item(item):
            try:
                # 메모리에서 이미지 객체를 꺼내고 딕셔너리에서 연결을 끊음 (RAM 확보)
                raw_img = item.pop("image_obj", None)
                if raw_img is None:
                    return None
                
                clean_img = self.preprocess_image(raw_img)
                cat = item.get("sub_category") or "PRODUCT"
                return clean_img, cat, item
            except Exception as e:
                print(f"'{item.get('summary_text', 'Unknown')}' 전처리 에러: {e}")
                return None

        # 시스템 과부하를 막기 위해 최대 8개의 스레드만 사용하여 In-Memory 이미지 병렬 전처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = executor.map(_process_item, search_results)
            
        for res in results:
            if res is not None:
                images.append(res[0])
                categories.append(res[1])
                items_with_images.append(res[2])
        
        if not images:
            return []
        
        # --- 모든 계산을 배치로 한번에 처리 ---
        
        # 2. 배치로 이미지 벡터 추출
        img_inputs = torch.stack([self.preprocess(img) for img in images]).to(self.device)
        if self.device == "cuda":
            img_inputs = img_inputs.to(torch.bfloat16)
        raw_img_vectors = F.normalize(self.model.encode_image(img_inputs), p=2, dim=1)
        
        # 3. 배치로 카테고리 벡터 추출
        cat_inputs = self.tokenizer(categories).to(self.device)
        cat_vectors = F.normalize(self.model.encode_text(cat_inputs), p=2, dim=1)
        
        # 4. [Stage 1] Semantic 스코어 일괄 계산
        # (1, D) vs (N, D) -> (N,)
        semantic_scores = F.cosine_similarity(query_vector, raw_img_vectors)
        
        # 5. [Stage 2] Aesthetic 스코어 일괄 계산
        # (N, D) - (N, D) -> (N, D)
        image_vectors = raw_img_vectors - (self.lambda_weight * cat_vectors)
        pure_image_vectors = F.normalize(image_vectors, p=2, dim=1)
        # (1, D) vs (N, D) -> (N,)
        aesthetic_scores = F.cosine_similarity(user_taste_vector, pure_image_vectors)

        print(f"쿼리와의 유사도 : {semantic_scores}")
        print(f"유저 취향과의 유사도 : {aesthetic_scores}")
        
        # 6. 결과 취합
        valid_results = []
        for i, item in enumerate(items_with_images):
            # 현재는 필터링 없이 모든 결과에 점수를 매김
            # if semantic_scores[i] < semantic_thresh or aesthetic_scores[i] < aesthetic_thresh:
            #     continue
            item["semantic_score"] = round(semantic_scores[i].item(), 4)
            item["aesthetic_score"] = round(aesthetic_scores[i].item(), 4)
            valid_results.append(item)
        
        # 메모리 정리
        for img in images:
            img.close()
        del images, img_inputs, raw_img_vectors, cat_inputs, cat_vectors, image_vectors, pure_image_vectors, semantic_scores, aesthetic_scores
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()
                
        return sorted(valid_results, key=lambda x: x["aesthetic_score"], reverse=True)
