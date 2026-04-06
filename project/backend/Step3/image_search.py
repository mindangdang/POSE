import os
import uuid
import asyncio
import httpx
from google import genai
from google.genai import types
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# client = genai.Client() # 전역 초기화 상태

# ==========================================
# 🎨 1. Gemini(Imagen 3) 가상 아이템 생성
# ==========================================
async def generate_vibe_image(user_query: str, user_vibe: str) -> bytes:
    """
    유저의 검색어와 취향을 조합하여 실존할 법한 완벽한 핏의 옷 이미지를 생성합니다.
    """
    # 옷의 질감과 핏이 잘 보이도록 프롬프트 엔지니어링 (영어 프롬프트가 성능이 더 좋음)
    enhanced_prompt = f"""
    High-end fashion editorial photography, a single clothing item: {user_query}. 
    The style and vibe should be: {user_vibe}. 
    Clean white studio background, photorealistic, 8k resolution, highly detailed texture and fabric.
    """
    
    try:
        # 최신 Imagen 3 모델 사용 (비동기 호출)
        response = await client.aio.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="3:4", # 패션/전신 샷에 최적화된 세로 비율
                output_mime_type="image/jpeg"
            )
        )
        print("🎨 [Image Gen] 가상 아이템 이미지 생성 완료!")
        # 생성된 이미지의 바이트 데이터 반환
        return response.generated_images[0].image.image_bytes
        
    except Exception as e:
        print(f"🚨 이미지 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="가상 아이템 생성에 실패했습니다.")


# ==========================================
# ☁️ 2. 클라우드 스토리지 임시 업로드 (SerpApi용)
# ==========================================
async def upload_to_public_storage(image_bytes: bytes) -> str:
    """
    생성된 이미지를 S3, Supabase 등에 업로드하고 퍼블릭 URL을 반환합니다.
    (아래는 임시 목업 코드입니다. 실제 사용하는 스토리지 로직으로 교체하세요.)
    """
    file_name = f"vibe_search_{uuid.uuid4().hex}.jpg"
    
    # TODO: Boto3(AWS) 또는 Supabase Client를 이용해 image_bytes 업로드 로직 구현
    # await s3_client.upload(...) 
    
    mock_public_url = f"https://your-storage-bucket.com/temp/{file_name}"
    print(f"☁️ [Storage] 이미지 업로드 완료: {mock_public_url}")
    
    return mock_public_url


# ==========================================
# 🔍 3. SerpApi 구글 렌즈 (사진 + 텍스트 멀티서치)
# ==========================================
async def run_google_lens_multisearch(image_url: str, text_query: str) -> list:
    """
    생성된 이미지 URL과 텍스트 필터(멀티서치)를 구글 렌즈에 던져 실제 상품을 찾습니다.
    """
    serp_api_key = os.environ.get("SERP_API_KEY")
    url = "https://serpapi.com/search"
    
    # Google Lens 엔진 파라미터 셋팅
    params = {
        "engine": "google_lens",
        "url": image_url,   # 시각적 핏/바이브 타겟팅 (생성된 이미지)
        "q": text_query,    # 팩트 타겟팅 (예: "나일론", "무신사") - 멀티서치 기능!
        "api_key": serp_api_key,
        "hl": "ko",
        "country": "kr"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # 구글 렌즈는 결과를 'visual_matches' 배열로 줍니다.
        matches = data.get("visual_matches", [])
        print(f"🔍 [Lens] 구글 렌즈 원본 검색 결과: {len(matches)}개")

        results = []
        for match in matches:
            # 썸네일과 원본 링크 추출
            thumbnail = match.get("thumbnail", "")
            link = match.get("link", "")
            title = match.get("title", "상품명 없음")
            source = match.get("source", "알 수 없는 샵") # 보통 쇼핑몰 이름이 나옴
            
            # 너무 관련 없는 사이트(핀터레스트, 위키 등)는 1차 제외
            if "pinterest" in link or "wikipedia" in link:
                continue

            results.append({
                "id": str(uuid.uuid4()),
                "category": "PRODUCT",
                "vibe": "AI가 그린 이미지와 똑같이 생긴 아이템",
                "image_url": thumbnail,
                "url": link,
                "summary_text": title,
                "facts": {
                    "title": title,
                    "Shop": source
                }
            })
            
        return results

    except Exception as e:
        print(f"🚨 구글 렌즈 검색 실패: {e}")
        return []


# ==========================================
# 🚀 4. 라우터 결합 (Visual Search Endpoint)
# ==========================================
class VisualSearchRequest(BaseModel):
    query: str       # 예: "초록색 투웨이 지퍼 숏자켓"
    focus_text: str  # 멀티서치에 쓸 팩트 키워드 (예: "나일론 무신사")
    user_vibe: str   # 예: "스트릿, 고프코어"

@router.post("/pse/visual")
async def visual_vibe_search(payload: VisualSearchRequest):
    try:
        # 1. 제미나이로 가상 이미지 생성
        image_bytes = await generate_vibe_image(payload.query, payload.user_vibe)
        
        # 2. 렌즈에 던지기 위해 퍼블릭 URL로 업로드
        image_url = await upload_to_public_storage(image_bytes)
        
        # 3. 사진(이미지) + 텍스트(소재/도메인) 동시 검색
        lens_results = await run_google_lens_multisearch(image_url, payload.focus_text)
        
        # 4. (선택 사항) 여기서 이전에 만든 'Vision 이진 분류기'를 한 번 더 태워서
        # 진짜 퀄리티 좋은 쇼핑몰인지 필터링하면 완벽함!
        
        return {"success": True, "results": lens_results}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))