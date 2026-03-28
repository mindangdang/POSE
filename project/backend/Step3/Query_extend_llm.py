import json
from google import genai
import os

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

async def optimize_query_with_llm(user_query: str, taste_profile: str, recent_items: str):
    """
    LLM을 사용해 검색어를 확장하고, 해당 쿼리에 맞는 힙한 사이트 화이트리스트를 생성합니다.
    """
    prompt = f"""
    당신은 트렌디한 큐레이션 검색 엔진 'Vibe Search'의 최고급 쿼리 최적화 에이전트입니다.
    사용자의 [현재 검색어], [취향 프로필], [최근 저장한 아이템]을 분석하여 다음 두 가지를 수행하세요.

    1. 검색어 확장 (optimized_query): 사용자의 취향에 맞춰 구글 검색에 최적화된 키워드를 생성하세요. 
    2. 타겟 도메인 추출 (whitelist_sites): 이 검색어의 카테고리(패션, 가구, 전자기기 등)에 가장 잘 맞는 고품질/힙한 브랜드, 편집숍, 매거진의 도메인(예: musinsa.com, kream.co.kr, ohou.se 등) 5~10개를 배열로 추천하세요.
       *주의: 쿠팡, 알리, 11번가, 네이버쇼핑 등 양산형 종합 쇼핑몰은 절대 포함하지 마세요.*

    [Input]
    - 현재 검색어: {user_query}
    - 취향 프로필: {taste_profile}
    - 최근 저장한 아이템 요약: {recent_items}

    [Output Format (반드시 유효한 JSON 형식으로만 응답할 것)]
    {{
        "optimized_query": "확장된 검색어 (예: 고프코어 테크웨어 바람막이 자켓)",
        "whitelist_sites": ["kream.co.kr", "musinsa.com", "heights-store.com", "worksout.co.kr"]
    }}
    """

    try:
        # Gemini 1.5 Flash (또는 Pro) 모델 사용 (JSON 모드 켜기!)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json" # 🔥 무조건 JSON으로 뱉게 강제!
            )
        )
        
        # LLM이 준 JSON 문자열을 파이썬 딕셔너리로 변환
        result_dict = json.loads(response.text)
        return result_dict

    except Exception as e:
        print(f"LLM 최적화 실패: {e}")
        # 실패할 경우를 대비한 기본값(Fallback)
        return {
            "optimized_query": user_query,
            "whitelist_sites": ["musinsa.com", "29cm.co.kr", "kream.co.kr", "ohou.se"]
        }