import json
import asyncio
import httpx
import os
from google import genai
from google.genai import types
from project.backend.app.core.settings import load_backend_env

load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        base_url=my_proxy_url
    )
)

JUNK_BRAND_DB = {"탑텐", "스파오", "지오다노", "양산형도매택A", "싸구려쇼핑몰B"}

# 동시에 처리할 최대 API 요청 수 (안전성을 위해 5~10 권장)
MAX_CONCURRENT_VISION_CALLS = 5

async def check_vibe_with_vision(http_client: httpx.AsyncClient, semaphore: asyncio.Semaphore, item: dict, user_vibe: str) -> dict:
    """
    세마포어를 통해 동시 실행 수를 제한하며 Vision LLM 이진 분류를 수행합니다.
    """
    # 세마포어 톨게이트: 자리가 날 때까지 대기하다가, 빈자리가 생기면 진입!
    async with semaphore:
        image_url = item.get("image_url")
        title = item.get("title", "")
        
        # 1. 썸네일 이미지 다운로드 (비동기)
        try:
            img_response = await http_client.get(image_url, timeout=5.0)
            img_response.raise_for_status()
            image_bytes = img_response.content
        except Exception as e:
            print(f"이미지 다운로드 실패 ({title}): {e}")
            item["vibe_match"] = "YES" # 이미지 다운 실패 시 텍스트만으로 보수적 통과
            return item

        system_instruction = f"""
        너는 시각적 감각이 뛰어난 패션 에디터야. 유저 취향: '{user_vibe}'
        
        첨부된 사진을 보고, 유저 취향과 맞는지 이진 분류(YES/NO)를 해줘.
        [판단 기준]
        - YES: 핏, 색감, 질감이 취향에 잘 어울리는 감도 높은 옷
        - NO: 촌스럽거나, 핏이 엉성하거나, 취향과 반대되는 무드
        
        응답 포맷 (순수 JSON 객체):
        {{ "match": "YES", "reason": "스트릿한 무드에 잘 맞음" }}
        """
        
        try:
            # 2. 비동기 Vision API 호출
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), 
                    f"상품명: {title} | 이 옷이 취향에 맞는지 판단해줘."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            
            result_data = json.loads(response.text)
            item["vibe_match"] = result_data.get("match", "YES")
            item["vision_reason"] = result_data.get("reason", "")
            
            return item
            
        except Exception as e:
            print(f"Vision 판단 실패 ({title}): {e}")
            item["vibe_match"] = "YES"
            return item


async def apply_hybrid_filtering_parallel(items: list, user_vibe: str) -> list:
    """
    1차 DB 캐시 필터링 후, 살아남은 항목들을 세마포어를 이용해 '안전하고 빠르게' 병렬 처리합니다.
    """
    print(f"1차 필터링 전: {len(items)}개")
    
    # ==================================================
    # 1차: DB 기반 초고속 정적 필터링 (동기 처리)
    # ==================================================
    db_passed_items = [
        item for item in items 
        if item.get("Shop", "") not in JUNK_BRAND_DB
    ]
    print(f"DB 필터 통과: {len(db_passed_items)}개 생존")
    
    if not db_passed_items:
        return []

    # ==================================================
    # 👁️‍🗨️ 2차: 세마포어 적용 Vision LLM 병렬 필터링
    # ==================================================
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_VISION_CALLS)
    
    # 커넥션 풀을 하나만 열어서 모든 요청이 공유 (네트워크 리소스 절약)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        # 모든 작업을 한 번에 이벤트 루프에 던지지만, 실행은 세마포어가 5개씩 통제함
        tasks = [
            check_vibe_with_vision(http_client, semaphore, item, user_vibe) 
            for item in db_passed_items
        ]
        # 병렬로 결과 수집
        vision_checked_items = await asyncio.gather(*tasks)
    
    # "YES" 판정받은 진짜배기만 남김
    final_items = [
        item for item in vision_checked_items 
        if item.get("vibe_match") == "YES"
    ]
    
    print(f"최종 Vision 필터 통과: {len(final_items)}개 최종 생존")
    return final_items