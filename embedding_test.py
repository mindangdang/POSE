import os
import asyncio
import numpy as np
from PIL import Image
from google import genai
from project.backend.app.core.settings import load_backend_env
from google.genai import types

load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

# 구글 API 클라이언트 초기화
my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        base_url=my_proxy_url
    )
)
MODEL_NAME = "gemini-embedding-2-preview" 

def calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    v1, v2 = np.array(vec1), np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

async def get_embedding(content) -> list[float]:
    res = await client.aio.models.embed_content(
        model=MODEL_NAME, 
        contents=content
    )
    return res.embeddings[0].values

async def run_similarity_poc():
    centroid_text = "스트릿,엘레강스,빈티지,섹시한,유니크한,차분한 색감,슬림한"
    text_vector = await get_embedding(centroid_text)
    test_images = {
        # [Match Group] 취향에 부합하는 그룹
        "Match 1 (나이키 샥스 오렌지)": "project/backend/insta_vibes/1fbe38c616db4a0ebffb8791932031a6.jpg",
        "Match 2 (시그니처 버뮤다)": "project/backend/insta_vibes/19047a9f77434385900a3e971b018316.jpg",
        "Match 3 (나폴레옹 자켓)": "project/backend/insta_vibes/873424eca62440a69bc7a2bc52434ea9.jpg",
        
        # [Mismatch Group] 취향과 거리가 먼 극단적 효율성/깔끔함 추구 그룹
        "Mismatch 1 (이상한 후드집업)": "project/backend/insta_vibes/9d0f55cafd8b43849454a115e0b240ea.jpg",
        "Mismatch 2 (이상한 셔츠)": "project/backend/insta_vibes/088db874a8614aa9ae9df1f1d8860bed.jpg",
        "Mismatch 3 (이상한 바지)": "project/backend/insta_vibes/a676ca5a70e240979e44a8e6e261c733.jpg"
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