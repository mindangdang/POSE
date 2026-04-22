import os
import asyncio
import numpy as np
from PIL import Image
from google import genai
from project.backend.app.core.settings import load_backend_env
from google.genai import types
import torch
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# ==========================================
# 1. Fashion-CLIP 모델 초기화
# ==========================================
model_id = "patrickjohncyh/fashion-clip"
print(f"[{model_id}] 모델 및 프로세서 로드 중 (초기 다운로드에 시간이 소요될 수 있습니다)...")
processor = CLIPProcessor.from_pretrained(model_id)
model = CLIPModel.from_pretrained(model_id)

# 연산 장치 설정 (가능한 경우 GPU 사용)
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
model.eval()

def calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    v1, v2 = np.array(vec1), np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

async def get_embedding(content) -> list[float]:
    if isinstance(content, str):
        inputs = processor(text=content, return_tensors="pt", padding=True, truncation=True).to(device)
        with torch.no_grad():
            features = model.get_text_features(**inputs)
    else:
        inputs = processor(images=content, return_tensors="pt").to(device)
        with torch.no_grad():
            features = model.get_image_features(**inputs)
    return features.pooler_output.cpu().numpy().tolist()[0]

async def run_similarity_poc():
    centroid_text = "스트릿,엘레강스,빈티지,섹시한,유니크한,차분한 색감,슬림한"
    text_vector = await get_embedding(centroid_text)
    test_images = {

    }

    results = []
    print("\n[이미지 분석] 각 이미지 벡터와 텍스트 벡터 간 유사도 계산 시작...")
    
    for label, path in test_images.items():
        try:
            img = Image.open(path).convert("RGB")
            img_vector = await get_embedding(img)
            score = calculate_cosine_similarity(text_vector, img_vector)
            results.append({"label": label, "score": score})
        except Exception as e:
            print(f"에러 발생 ({label}): {e}")

    # 점수 기준 내림차순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)

    # ==========================================
    # 4. POC 결과 리포트 출력
    # ==========================================
    print("\n[POC 연산 결과 리포트]")
    print("-" * 50)
    for rank, item in enumerate(results, 1):
        print(f"{rank}위 | {item['score']:.4f} | {item['label']}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_similarity_poc())