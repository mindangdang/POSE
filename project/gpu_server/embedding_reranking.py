import os
import torch
import torch.nn.functional as F
from PIL import Image
import open_clip


# 멀티스레딩 억제로 CPU/RAM 스파이크 방지
os.environ["OMP_NUM_THREADS"] = "1"
if os.environ.get("HF_HUB_OFFLINE") is None:
    os.environ["HF_HUB_OFFLINE"] = "1"  


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
        self.cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        self.hf_offline = os.environ.get("HF_HUB_OFFLINE", "0")
        print(f"OpenCLIP 로드 설정: HF_HUB_OFFLINE={self.hf_offline}, cache_dir={self.cache_dir}")

        # open_clip을 통한 모델 및 전처리 모듈 로드
        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_id,
                cache_dir=self.cache_dir
            )
        except OSError as e:
            print(f"OpenCLIP 모델 로드 실패: {e}")
            if self.hf_offline == "1":
                print("HF_HUB_OFFLINE=1로 인해 로컬 캐시만 사용하도록 설정되어 있습니다. 온라인 다운로드를 시도합니다.")
                os.environ["HF_HUB_OFFLINE"] = "0"
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    self.model_id,
                    cache_dir=self.cache_dir
                )
            else:
                raise

        try:
            self.tokenizer = open_clip.get_tokenizer(
                self.model_id,
                cache_dir=self.cache_dir
            )
        except OSError as e:
            print(f"OpenCLIP 토크나이저 로드 실패: {e}")
            if self.hf_offline == "1":
                print("HF_HUB_OFFLINE=1로 인해 로컬 캐시만 사용하도록 설정되어 있습니다. 온라인 다운로드를 시도합니다.")
                os.environ["HF_HUB_OFFLINE"] = "0"
                self.tokenizer = open_clip.get_tokenizer(
                    self.model_id,
                    cache_dir=self.cache_dir
                )
            else:
                raise

        if self.device == "cuda":
            self.model = self.model.to(torch.bfloat16)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # torch.compile은 성능을 향상시키지만 초기 컴파일 시 메모리 사용량이 급증하여 프로세스가 종료될 수 있습니다.
        # 저사양 환경에서는 USE_TORCH_COMPILE=0 환경변수를 통해 비활성화할 수 있습니다.
        if os.environ.get("USE_TORCH_COMPILE", "1") == "1":
            print("torch.compile() 활성화됨. 첫 실행 시 컴파일로 인해 시간이 소요될 수 있습니다.")
            self.model = torch.compile(self.model)
        else:
            print("torch.compile() 비활성화됨. (추론 성능보다 안정성 우선)")

        print("모델 웜업 진행 중 (Dummy 데이터 실행)...")
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
    def get_image_vector(self, img: Image.Image) -> list[float]:
        """단일 이미지와 카테고리를 받아 Image Vector를 반환합니다. (DB 저장용)"""
        clean_img = self.preprocess_image(img)
        
        image_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
        if self.device == "cuda":
            image_input = image_input.to(torch.bfloat16)
 
        
        image_features = self.model.encode_image(image_input)
        img_vec = F.normalize(image_features, p=2, dim=1)
        
        return img_vec[0].tolist()

    
    def encode_text(self, text: str) -> torch.Tensor:
        """쿼리 텍스트를 SigLIP 텍스트 임베딩으로 인코딩"""
        with torch.no_grad():
            text_input = self.tokenizer([text]).to(self.device)
            text_vector = F.normalize(self.model.encode_text(text_input), p=2, dim=1)
        return text_vector

    def calculate_cosine_similarity(self, vec1: torch.Tensor, vec2: torch.Tensor) -> float:
        return F.cosine_similarity(vec1, vec2, dim=1).item()