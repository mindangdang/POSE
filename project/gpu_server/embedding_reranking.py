import os
import torch
import torch.nn.functional as F
from PIL import Image
import open_clip


# 멀티스레딩 억제로 CPU/RAM 스파이크 방지
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1" # 캐시 되어 있는 모델이 없는 경우에 0으로 설정. ls -la ~/.cache/huggingface/hub/로 확인

class FashionSiglipReRankingPipeline:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FashionSiglipReRankingPipeline, cls).__new__(cls)
            cls._instance._is_initialized = False
        return cls._instance

    def __init__(self):
        if self._is_initialized:
            return
            
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
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
        
        dot_product = torch.sum(img_vec * text_vec, dim=1, keepdim=True)
        projection = dot_product * text_vec
        pure_vibe = img_vec - projection
        image_vector = F.normalize(pure_vibe, p=2, dim=1)
        
        return image_vector[0].tolist()

    @torch.no_grad()
    def build_user_taste_vector(
        self, 
        pure_vibe_vectors: list[list[float]], 
        num_iterations: int = 5, 
        temperature: float = 12.0, 
        momentum: float = 0.15
    ) -> dict:
        """
        사용자의 취향 벡터(Pure Vibe) 기반으로 Hybrid Preference Score 계산을 위해
        Consensus(전체 무드)와 Memory(원본 위시리스트 벡터)를 함께 반환합니다.
        """
        if not pure_vibe_vectors:
            return None
            
        # 1. 텐서 변환 및 디바이스/데이터타입 할당
        vibe_tensor = torch.tensor(pure_vibe_vectors, device=self.device)
        if self.device == "cuda":
            vibe_tensor = vibe_tensor.to(torch.bfloat16)
            
        # 2. 모든 입력 벡터 정규화 (보안 및 연산 안정성 확보)
        x = F.normalize(vibe_tensor, p=2, dim=1)
            
        # 아이템이 1개뿐이라면 합의 알고리즘이 무의미하므로 정규화 후 바로 반환 (Shape: 1, 768)
        if vibe_tensor.size(0) == 1:
            return {"consensus": x, "memory": x}

        # 3. 초기 합의점(Consensus) 설정: 단순 평균
        # keepdim=True를 유지하여 Shape을 (1, 768)로 맞춤
        consensus = F.normalize(x.mean(dim=0, keepdim=True), p=2, dim=1)

        # 4. Iterative Consensus Refinement (반복적 합의 도출)
        for _ in range(num_iterations):
            # 4.1 현재 합의점과 각 아이템 벡터 간의 유사도 측정
            similarities = F.cosine_similarity(x, consensus, dim=1)

            # 4.2 Anti-aligned 억제: 음의 상관관계를 가지는 벡터 방향성 무시 (0으로 클램핑)
            similarities = torch.clamp(similarities, min=0.0)

            # 4.3 가중치 부여 (Temperature Scaling & Softmax)
            # 합의점과 가까울수록 가중치를 기하급수적으로 높이고, 멀수록 낮춤
            weights = F.softmax(similarities * temperature, dim=0)

            # 4.4 가중치가 반영된 새로운 방향성(Refined) 산출
            refined = torch.sum(weights.unsqueeze(-1) * x, dim=0, keepdim=True)
            refined = F.normalize(refined, p=2, dim=1)

            # 4.5 Momentum 업데이트: 
            # 한 번의 이터레이션에서 합의점이 너무 급격히 튀는 것을 방지하고 부드럽게 수렴시킴
            consensus = F.normalize((1.0 - momentum) * consensus + momentum * refined, p=2, dim=1)
            
        # 최종 도출된 공통 취향 벡터와 위시리스트 메모리를 함께 반환
        return {"consensus": consensus, "memory": x}
    
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
        user_taste_profile: dict,
        query_vector: torch.Tensor,
        semantic_thresh: float = 0, 
        aesthetic_thresh: float = 0.45,
        alpha: float = 0.3 # Consensus score의 비중. (1 - alpha)는 Prototype score의 비중.
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
            if query_vector is not None and query_vector.dim() == 1:
                query_vector = query_vector.unsqueeze(0)
                
            consensus_vector = user_taste_profile.get("consensus")
            memory_vectors = user_taste_profile.get("memory")
            
            if consensus_vector is not None and consensus_vector.dim() == 1:
                consensus_vector = consensus_vector.unsqueeze(0)
            if memory_vectors is not None and memory_vectors.dim() == 1:
                memory_vectors = memory_vectors.unsqueeze(0)
            
            # 1. 이미지 및 카테고리 벡터 추출
            img_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
            if self.device == "cuda":
                img_input = img_input.to(torch.bfloat16)
            raw_img_vector = F.normalize(self.model.encode_image(img_input), p=2, dim=1)

            cat_input = self.tokenizer([cat]).to(self.device)
            cat_vector = F.normalize(self.model.encode_text(cat_input), p=2, dim=1)
            
            # 2. Stage 1 & 2 스코어 일괄 계산
            semantic_score = F.cosine_similarity(query_vector, raw_img_vector).item()
            dot_product = torch.sum(raw_img_vector * cat_vector, dim=1, keepdim=True)
            projection = dot_product * cat_vector
            pure_vibe = raw_img_vector - projection
            pure_image_vector = F.normalize(pure_vibe, p=2, dim=1)
            
            # Hybrid Preference Score 계산 (Consensus + Prototype)
            consensus_score = F.cosine_similarity(consensus_vector, pure_image_vector).item()
            
            # Prototype Score: Memory 벡터들과의 유사도 중 최대값 (Max Similarity)
            similarities = F.cosine_similarity(pure_image_vector, memory_vectors)
            prototype_score = similarities.max().item()
            
            aesthetic_score = (alpha * consensus_score) + ((1.0 - alpha) * prototype_score)
            
            clean_img.close()
            
            print(f"[{item.get('summary_text', 'Unknown')}] Semantic: {semantic_score:.4f} / Aesthetic: {aesthetic_score:.4f} (Consensus: {consensus_score:.4f}, Prototype: {prototype_score:.4f})")

            if aesthetic_score < aesthetic_thresh:
                return None
            
            else:
                item["semantic_score"] = round(semantic_score, 4)
                item["aesthetic_score"] = round(aesthetic_score, 4)
                item["consensus_score"] = round(consensus_score, 4)
                item["prototype_score"] = round(prototype_score, 4)
                return item
        
        except Exception as e:
            print(f"'{item.get('summary_text', 'Unknown')}' 단일 평가 에러: {e}")
            return None
