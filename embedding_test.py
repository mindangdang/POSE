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

async def score_image_aesthetics(image_path: str, centroid_text: str) -> dict:
    """Vision LLM을 사용하여 이미지의 미학적 부합도를 0~100점으로 직접 채점합니다."""
    
    system_prompt = f"""
    당신은 하이엔드 패션 매거진의 수석 에디터입니다.
    유저의 핵심 취향(Aesthetic Centroid)은 다음과 같습니다: [{centroid_text}]
    
    제공된 이미지를 분석하여, 위 취향과의 시각적/형태학적 일치도를 0에서 100 사이의 점수로 평가하십시오.
    
    [평가 기준]
    1. 아이템의 종류(신발, 바지, 자켓 등)는 감점 요인이 아닙니다. 오직 '무드', '질감', '실루엣', '디테일'이 취향 텍스트와 일치하는지만 봅니다.
    2. 양산형 패션, 지나치게 깔끔하고 매끄러운 핏, 뻔한 디자인은 엄격하게 감점하십시오.
    
    반드시 다음 JSON 구조로만 반환하십시오.
    {{"score": 85}}
    """
    
    img = Image.open(image_path)
    
    try:
        res = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, "이 상품의 미학적 점수를 평가해."],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        # JSON 파싱하여 반환 (실제 구현 시 pydantic 스키마 사용 권장)
        import json
        return json.loads(res.text)
    except Exception as e:
        print(f"채점 에러: {e}")
        return {"score": 0}

async def run_similarity_poc():

    test_images = {
        # [Match Group] 취향에 부합하는 그룹
        "Match 1 (나이키 샥스 오렌지)": "project/backend/insta_vibes/1fbe38c616db4a0ebffb8791932031a6.jpg",
        "Match 2 (시그니처 버뮤다)": "project/backend/insta_vibes/19047a9f77434385900a3e971b018316.jpg",
        "Match 3 (나폴레옹 자켓)": "project/backend/insta_vibes/873424eca62440a69bc7a2bc52434ea9.jpg",
        "(apuee)": "project/backend/insta_vibes/9f9e22ed641b45d6b2f1888eb30fc0e6.jpg",
        "(예쁜 후집)": "project/backend/insta_vibes/55aad7feb5fe4c07baca853790c9a55f.jpg",
        "(두가티)": "project/backend/insta_vibes/40450bef65c04c06a5b6b2851ed566a6.jpg",
        "(자수 포인트 바지)": "project/backend/insta_vibes/42549f6dfa1047068e901d2efa5eff7d.jpg",
        "(오퍼스 반팔)": "project/backend/insta_vibes/a8b5d9090f28489494290d387c6452e4.jpg",
        "(헨리넥)": "project/backend/insta_vibes/fa2b59eee03e4cfe8e775d3f85b4f47f.jpg",
        # [Mismatch Group] 취향과 거리가 먼 극단적 효율성/깔끔함 추구 그룹
        "Mismatch 1 (이상한 후드집업)": "project/backend/insta_vibes/9d0f55cafd8b43849454a115e0b240ea.jpg",
        "Mismatch 2 (이상한 셔츠)": "project/backend/insta_vibes/088db874a8614aa9ae9df1f1d8860bed.jpg",
        "Mismatch 3 (이상한 바지)": "project/backend/insta_vibes/a676ca5a70e240979e44a8e6e261c733.jpg"
    }

    results = []
    center_text = "vintage elegant streetwear, avant-garde aesthetic, slim form-fitting silhouette, asymmetric design, sheer or cut-out details, muted neutral color palette"

    for label, path in test_images.items():
        try:

            score = await score_image_aesthetics(path, center_text) 
            results.append({"score": score.get("score", 0)})
            print(f"{label}: {score.get('score', 0)}")
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
        print(f"{rank}위 | {item['score']:.4f}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_similarity_poc())