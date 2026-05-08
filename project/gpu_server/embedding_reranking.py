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
        
        print("User Vector 합성을 위한 Attention 레이어 로드 중...")
        # 768차원 벡터를 8개의 Head로 나누어 다각도로 공통점을 찾습니다.
        self.attention = torch.nn.MultiheadAttention(embed_dim=768, num_heads=8, batch_first=True).to(self.device)
        if self.device == "cuda":
            self.attention = self.attention.to(torch.bfloat16)
        print("Attention 레이어 로드 완료.")

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
    def build_user_taste_vector(self, pure_vibe_vectors: list[list[float]]) -> torch.Tensor:
        if not pure_vibe_vectors:
            return None
            
        # 1. N개의 무드 벡터를 PyTorch 텐서로 변환: Shape (N, 768)
        vibe_tensor = torch.tensor(pure_vibe_vectors, device=self.device)
        if self.device == "cuda":
            vibe_tensor = vibe_tensor.to(torch.bfloat16)
            
        # 아이템이 1개뿐이라면 어텐션이 무의미하므로 바로 반환
        if vibe_tensor.size(0) == 1:
            return F.normalize(vibe_tensor, p=2, dim=1)

        # 2. Attention 연산을 위해 Batch 차원 추가: Shape (1, N, 768)
        vibe_batch = vibe_tensor.unsqueeze(0)
        
        # 3. Self-Attention 실행 (Query, Key, Value 모두 자신의 위시리스트)
        # 각 옷이 다른 옷들을 바라보며 "나와 비슷한 무드"에만 높은 가중치를 부여합니다.
        attn_output, attn_weights = self.attention(
            query=vibe_batch, 
            key=vibe_batch, 
            value=vibe_batch
        )
        # attn_output Shape: (1, N, 768)
        
        # 4. 잔차 연결 (Residual Connection) - 트랜스포머의 정석
        # 원본 무드와 어텐션으로 증폭된 무드를 더해줍니다.
        contextualized_vibes = vibe_batch + attn_output
        
        # 5. 최종 결합: 이제 단순 평균(Mean)을 내도 안전합니다.
        # 왜냐하면 어텐션을 통해 '서로 공통점이 없는 특이값(Outlier)'은 이미 억제되었고,
        # '공통된 무드'만 수치적으로 증폭되었기 때문입니다.
        consensus_vector = torch.mean(contextualized_vibes.squeeze(0), dim=0, keepdim=True)
        
        # 6. 크기를 1로 맞춰 코사인 유사도 연산이 가능하게 정규화
        return F.normalize(consensus_vector, p=2, dim=1)
    
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
        semantic_thresh: float = 0, # semantic: 0.0274 쿼리 / Aesthetic: 0.5170 취향벡터
        aesthetic_thresh: float = 0.45
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
            if user_taste_vector is not None and user_taste_vector.dim() == 1:
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
            dot_product = torch.sum(raw_img_vector * cat_vector, dim=1, keepdim=True)
            projection = dot_product * cat_vector
            pure_vibe = raw_img_vector - projection
            pure_image_vector = F.normalize(pure_vibe, p=2, dim=1)
            aesthetic_score = F.cosine_similarity(user_taste_vector, pure_image_vector).item()
            clean_img.close()
            
            print(f"[{item.get('summary_text', 'Unknown')}] Semantic: {semantic_score:.4f} / Aesthetic: {aesthetic_score:.4f}")

            if aesthetic_score < aesthetic_thresh:
                return None
            
            else:
                item["semantic_score"] = round(semantic_score, 4)
                item["aesthetic_score"] = round(aesthetic_score, 4)
                return item
        
        except Exception as e:
            print(f"'{item.get('summary_text', 'Unknown')}' 단일 평가 에러: {e}")
            return None
