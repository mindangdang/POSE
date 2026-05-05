import os
import torch
import torch.nn.functional as F
from PIL import Image
import open_clip


# 멀티스레딩 억제로 CPU/RAM 스파이크 방지
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1" # 캐시 되어 있는 모델이 없는 경우에 0으로 설정. ls -la ~/.cache/huggingface/hub/로 확인
os.environ["HF_HOME"] = os.path.abspath("project/gpu_server/models")

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
        self.model = torch.compile(self.model)
        
        print("모델 웜업 진행 중 (Dummy 데이터 컴파일 수행)...")
        try:
            with torch.no_grad():
                dummy_img = Image.new("RGB", (224, 224), "WHITE")
                dummy_img_input = self.preprocess(dummy_img).unsqueeze(0).to(self.device)
                if self.device == "cuda":
                    dummy_img_input = dummy_img_input.to(torch.bfloat16)
                dummy_text_input = self.tokenizer(["warmup"]).to(self.device)
                
                self.model.encode_image(dummy_img_input)
                self.model.encode_text(dummy_text_input)
            print("모델 웜업 완료.")
        except Exception as e:
            print(f"모델 웜업 중 에러 발생 (무시됨): {e}")

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
        """단일 이미지와 카테고리를 받아 Image Vector를 반환합니다. (DB 저장용)"""
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
    def evaluate_single_item(
        self,
        item: dict,
        user_taste_vector: torch.Tensor,
        query_vector: torch.Tensor,
        semantic_thresh: float = 0.10, # semantic: 0.0274 쿼리 / Aesthetic: 0.5170 취향벡터
        aesthetic_thresh: float = 0.0
    ) -> dict | None:
        """단일 아이템 처리: 전처리 -> 임베딩 -> 스코어 계산 -> 임계값 통과 시 반환"""
        raw_img = item.pop("image_obj", None)
        if raw_img is None:
            return None
            
        try:
            clean_img = self.preprocess_image(raw_img)
            raw_img.close()
            cat = item.get("sub_category") or "PRODUCT"
            
            # 연산을 위해 1D 벡터가 들어왔을 경우 2D 벡터로 보정 (dim=1 연산 에러 방지)
            if query_vector.dim() == 1:
                query_vector = query_vector.unsqueeze(0)
            if user_taste_vector.dim() == 1:
                user_taste_vector = user_taste_vector.unsqueeze(0)
            
            # 1. 이미지 및 카테고리 벡터 추출
            img_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
            if self.device == "cuda":
                img_input = img_input.to(torch.bfloat16)
            raw_img_vector = F.normalize(self.model.encode_image(img_input), p=2, dim=1)

            cat_input = self.tokenizer([cat]).to(self.device)
            cat_vector = F.normalize(self.model.encode_text(cat_input), p=2, dim=1)
            
            # 2. Stage 1 & 2 스코어 일괄 계산
            semantic_score = F.cosine_similarity(query_vector, raw_img_vector).item()
            image_vector = raw_img_vector - (self.lambda_weight * cat_vector)
            pure_image_vector = F.normalize(image_vector, p=2, dim=1)
            aesthetic_score = F.cosine_similarity(user_taste_vector, pure_image_vector).item()
            clean_img.close()
            
            print(f"[{item.get('summary_text', 'Unknown')}] Semantic: {semantic_score:.4f} / Aesthetic: {aesthetic_score:.4f}")

            #if semantic_score < semantic_thresh or aesthetic_score < aesthetic_thresh:
                #return None
                
            item["semantic_score"] = round(semantic_score, 4)
            item["aesthetic_score"] = round(aesthetic_score, 4)
            return item
        except Exception as e:
            print(f"'{item.get('summary_text', 'Unknown')}' 단일 평가 에러: {e}")
            return None
