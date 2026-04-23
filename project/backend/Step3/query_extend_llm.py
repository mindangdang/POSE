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
    당신은 대형 이커머스 데이터베이스(무신사, 크림 등)에서 양산형 의류를 걸러내고 '고감도 매물'만을 정밀 타겟팅하는 검색 쿼리 엔지니어다.
    유저의 추상적인 자연어 검색어를 구글 검색 엔진이 가장 정확하게 파싱할 수 있는 엄격한 Boolean 쿼리로 변환하라.

    [쿼리 변환 규칙]
    1. 객체분할: 유저 검색어를 '중심어(Anchor)','디테일/무드(Variable)','핏(Fit)','색상(Color)'으로 정확하게 판단하여 분리하라.
    2. 중심어 동의어 확장: Anchor는 동일한 카테고리의 유의어 2~3개로 확장하여 OR 연산으로 묶어라. (예: 청바지 -> 데님 팬츠 OR 데님 진 OR 청바지)
    3. 속성어 키워드 변환: Variable은 다양한 패션 용어(ex:스트릿, 빈티지, 가먼트 다잉 워싱, 파워숄더 등)로 번역 및 확장하여 OR 연산으로 묶어라.
    4. 유연한 처리: 핏과 색상이 유저 검색어에서 감지 되지 않았을 경우 비워두어라.
    5. 강제 구조: 반드시 `(Anchor_1 OR Anchor_2) AND (Variable_1 OR Variable_2 OR Variable_3) AND ....` 형태의 문법을 엄수하라.
    6. 할루시네이션 방지: 유저의 쿼리가 이미 상품군이 특정되도록 충분한 정보를 담고 있는 경우 유저의 쿼리를 그대로 사용하라. (ex:웨스턴 벨트 -> 더 이상 확장할 것 없음)
    7. 확장 제한: 각 차원별 단어는 최대 4개까지만 생성하고 OR 연산으로 묶어라.

    [Examples]
    입력: "스트릿 데님" 
    출력: 
    {{
    "final_query": "(\\"데님 팬츠\\" OR \\"데님 진\\" OR \\"청바지\\") AND (\\"벌룬 핏\\" OR \\"와이드\\" OR \\"플레어\\") AND (\\"캣워싱\\" OR \\"도밍고\\" OR \\"디스트로이드\\")"
    }}
    입력: "빈티지한 브라운 가죽자켓" 
    출력:
    {{
    "final_query": "(\\"가죽자켓\\" OR \\"라이더자켓\\" OR \\"바이커자켓\\") AND (\\"브라운\\") AND (\\"빈티지\\" OR \\"아카이브\\" OR \\"디스트레스드\\")"
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
