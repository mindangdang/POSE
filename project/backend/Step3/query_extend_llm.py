import json
from google import genai
import os
from google.genai import types
from project.backend.app.core.settings import load_backend_env
from project.backend.app.core.resilience import with_llm_resilience


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

@with_llm_resilience(fallback_default=lambda user_query: {"final_query": user_query})
async def optimize_query_with_llm(user_query: str):

    prompt = f"""
    [System Persona]
    당신은 하이엔드 스트릿, 아카이브, 디자이너 브랜드 패션 도메인에 특화된 검색 쿼리 엔지니어다.
    유저의 추상적인 자연어 검색어를 구글 검색 엔진이 가장 정확하게 파싱할 수 있는 엄격한 Boolean 쿼리로 변환하라.

    [Core Rules]
    1. 분리의 원칙: 유저 검색어를 '순수 아이템 명칭(Anchor)'과 '디테일/무드(Variable)'로 완벽하게 분리하라. 중심어에는 어떠한 수식어도 붙어선 안된다.
    2. 중심어 동의어 확장: Anchor는 검색 엔진 타율을 높이기 위해 동일한 카테고리의 유의어 2~3개로 확장하여 OR 연산으로 묶어라. (예: 청바지 -> 데님 팬츠 OR 데님 진 OR 청바지)
    3. 속성어 실전 키워드 변환: Variable은 무신사,크림 등 트렌디한 편집샵의 상품명에 자주 사용되는 용어(소재, 핏, 실루엣, 무드)로 번역 및 확장하여 OR 연산으로 묶어라.
    4. 강제 구조: 반드시 `(Anchor_1 OR Anchor_2) AND (Variable_1 OR Variable_2 OR Variable_3)` 형태의 문법을 엄수하라.

    [Few-Shot Examples]
    입력: "스트릿한 배기진"
    출력: 
    {{
    "final_query": "(\\"데님 팬츠\\" OR \\"데님 진\\" OR \\"청바지\\") AND (\\"배기 핏\\" OR \\"스트릿\\" OR \\"벌룬 핏\\" OR \\"와이드\\" OR \\"플레어\\")"
    }}
    입력: "어깨 넓어보이는 숏자켓"
    출력:
    {{
    "final_query": "(\\"자켓\\" OR \\"블루종\\" OR \\"아우터\\") AND (\\"크롭\\" OR \\"숏기장\\") AND (\\"와이드 숄더\\" OR \\"파워 숄더\\" OR \\"오버 핏\\" OR \\"스트릿\\")"
    }}

    입력: "워싱 들어간 롱슬리브"
    출력:
    {{
    "final_query": "(\\"롱슬리브\\" OR \\"긴팔 티셔츠\\" OR \\"롱티\\") AND (\\"가먼트 다잉\\" OR \\"피그먼트\\" OR \\"빈티지 워싱\\")"
    }}

    반드시 순수 JSON 객체 포맷으로만 반환하라.

    현재 입력: {user_query} 
    """

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1 
        )
    )
    
    return json.loads(response.text)
