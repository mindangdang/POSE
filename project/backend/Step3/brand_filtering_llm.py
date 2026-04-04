import os
import json
import asyncio
from google import genai
from google.genai import types
from project.backend.config import load_backend_env

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

async def filter_brand_chunk(brands_chunk: list, user_query: str, user_vibe: str) -> dict:
    """
    브랜드 리스트 청크(묶음)를 Gemini Client로 평가합니다.
    """
    if not brands_chunk:
        return {}
        
    brands_str = ", ".join(brands_chunk)
    
    system_instruction = f"""
    너는 패션 트렌드와 브랜드 포지셔닝을 완벽하게 이해하는 AI 문지기야.
    현재 유저의 취향 프로필은 '{user_vibe}'이며, 방금 '{user_query}'를 검색했어.
    
    다음 브랜드 목록을 평가해서, 상태(JUNK, PASS, DROP)를 지정해줘.
    
    [평가 기준]
    1. JUNK (영구 차단): 동대문 사입/택갈이, 초저가 양산형, 듣보잡 쇼핑몰.
    2. PASS (무조건 통과): 검증된 디자이너, 스트릿 '느좋' 브랜드.
    3. DROP (조건부 차단): 유니클로 등 대중적/SPA 브랜드 중 유저의 현재 쿼리나 취향과 안 맞는 경우. (기본템 쿼리면 PASS)
       
    응답 포맷 (순수 JSON 배열):
    [
      {{"brand": "브랜드명", "status": "PASS"}},
      {{"brand": "브랜드명2", "status": "DROP"}}
    ]
    """
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash", 
            contents=brands_str,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        evaluations = json.loads(response.text)
        return {item["brand"]: item["status"] for item in evaluations}
        
    except Exception as e:
        print(f"청크 필터링 실패: {e}")
        return {brand: "PASS" for brand in brands_chunk} 

async def process_and_filter_items(items: list, user_query: str, user_vibe: str) -> list:
    """
    SerpApi에서 가져온 N개의 아이템을 비동기로 동시에 필터링합니다.
    """
    # N개의 아이템에서 중복을 제거한 고유 브랜드 목록 추출
    unique_brands = list(set(item.get("shop", "알 수 없는 샵") for item in items if item.get("shop")))
    
    # API 부하를 막기 위해 브랜드를 15개 단위(Chunk)로 쪼개기
    chunk_size = 15
    brand_chunks = [unique_brands[i:i + chunk_size] for i in range(0, len(unique_brands), chunk_size)]
    
    # 쪼개진 청크들을 asyncio.gather를 이용해 '동시에(병렬)' 처리
    tasks = [filter_brand_chunk(chunk, user_query, user_vibe) for chunk in brand_chunks]
    chunk_results = await asyncio.gather(*tasks)
    
    # 6. 여러 청크에서 온 결과를 하나의 딕셔너리로 병합
    brand_status_map = {}
    for res in chunk_results:
        brand_status_map.update(res)
        
    print(brand_status_map)
    
    filtered_items = [
        item for item in items 
        if brand_status_map.get(item.get("shop", ""), "PASS") == "PASS"
    ]
    
    return filtered_items
