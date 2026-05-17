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
    당신은 추상적인 패션 검색어를 구체화하고 최적화하는 검색 쿼리 엔지니어다. 구글 검색 엔진이 가장 정확하게 파싱할 수 있는 엄격한 Boolean 쿼리로 변환하라.

    [쿼리 변환 규칙]
    1. 객체분할: 유저 검색어에서 '중심어(Anchor)','디테일/무드(Variable)','핏(Fit)','색상(Color)'를 추출하라.
    2. 중심어 동의어 확장: Anchor,Fit,Color,Variable를 유의어로 확장하라. (예: 청바지 -> 데님 팬츠 OR 데님 진 OR 청바지)
    3. 속성어 키워드 변환: Variable의 추상적인 무드 키워드를 구체적인 디테일/무드 키워드로 변환하라. (ex:스트릿 -> 가먼트 다잉 워싱, 크롭, 빈티지 등)
    4. 유연한 처리: 각 항목이 유저 검색어에서 감지 되지 않았을 경우 비워두어라.
    5. 강제 구조: 반드시 `(Anchor_1 OR Anchor_2) AND (Variable_1 OR Variable_2 OR Variable_3) AND ....` 형태의 문법을 엄수하라.
    6. 할루시네이션 방지: 동의어가 없는 경우 억지로 확장하지 말고 유저 쿼리를 그대로 사용하라. (ex:블랙 웨스턴 벨트 -> 더 이상 확장할 것 없음)
    7. 확장 제한: 각 차원별 단어는 최대 4개까지만 생성하고 OR 연산으로 묶어라.
    8. 유저 쿼리가 구체적인 브랜드나 아이템명을 포함하는 경우, 동의어 확장을 하지 않는다. (ex: 나이키 에어맥스 90 -> 확장 금지)
    9. Boolean 쿼리와 함께 입력쿼리의 중심어를 영어로 단순 번역한 쿼리를 같이 반환하라.  

    [Examples]
    입력: "연청 플레어 진" 
    출력: 
    {{
    "final_query": "(\\"연청\\" OR \\"라이트 블루\\" OR \\"스카이 블루\\") AND (\\"플레어\\" OR \\"세미플레어\\" OR \\"부츠컷\\") AND (\\"데님 팬츠\\" OR \\"진\\" OR \\"데님\\")"
    "translated_query": "jeans"
    }}
    입력: "빈티지한 브라운 가죽자켓" 
    출력:
    {{
    "final_query": "(\\"빈티지\\" OR \\"아카이브\\") AND (\\"브라운\\") AND (\\"가죽자켓\\" OR \\"라이더자켓\\" OR \\"레더자켓\\" OR \\"램스킨자켓\\" )"
    "translated_query": "jacket"
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
