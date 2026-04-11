import json
from google import genai
import os
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

async def optimize_query_with_llm(user_query: str):

    prompt = f"""
    너는 무신사, 크림, 29CM 등 최상위 패션 플랫폼과 디자이너 브랜드의 실제 상품명(Title) 패턴을 완벽히 분석하고 적용하는 SEO 검색 엔진 마스터야. 
    유저의 검색어가 입력되면, 실제 브랜드 MD들이 기입하는 '전문 용어' 및 '실전 키워드'로 번역하여 최상의 구글 검색 결과를 가져올 수 있는 정교한 확장 쿼리를 생성해야 해.

    [핵심 원칙]
    1. 객관성 유지: 유저의 주관적인 취향이나 프로필을 임의로 추론하여 쿼리에 반영하지 마라. 오직 입력된 검색어의 객관적인 상품 특성과 패턴 확장에만 집중하라.
    2. 구조화된 쿼리: 구글 검색 엔진이 가장 잘 이해하는 형태인 `"핵심 공통어" (속성어1 OR 속성어2)` 구조를 반드시 엄수하라.

    [변환 규칙]
    1. Anchor(핵심어): 유저 검색어의 본질이 되는 아이템명과 핏을 조합하여 따옴표("")로 묶어라. (예: "와이드 데님 팬츠")
    2. Variable(속성어/디테일): 검색어에 내포된 소재, 디테일, 영문 혼용 트렌드 용어를 추출하여 괄호 안에 `OR` 연산자로 묶어라.

    [실제 브랜드 상품명 패턴 학습 (Few-Shot Examples)]
    - 영문 혼용/트렌드 용어: 청자켓 -> 트러커 자켓 / 츄리닝 -> 스웨트 팬츠, 조거 팬츠, 트랙 팬츠 / 숏패딩 -> 푸퍼, 다운 점퍼
    - 소재 명시: 레더, 피그먼트, 가먼트 다잉, 워시드, 헤어리 알파카, 셀비지
    - 핏/디테일 명시: 투턱, 핀턱, 투웨이 지퍼, 파라슈트, 카고, 와이드, 플레어 핏, 벌룬 핏, 컷아웃, 디스트로이드

    [학습된 패턴 적용 예시]
    입력: "숏패딩"
    출력: {{'final_query': "\"다운 점퍼\" (푸퍼 OR 라이트웨이트 OR 헤비아우터)"}}

    입력: "워싱 데님"
    출력: 
    {{'final_query': "\"워시드 데님 팬츠\" (가먼트 다잉 OR 빈티지 워싱 OR 엠보스드 OR 피그먼트)"}}


    반드시 아래의 순수 JSON 객체 포맷으로만 반환해:
    {"생성된 쿼리 문자열"}

    현재 입력된 유저의 쿼리: {user_query}
    """

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1 
            )
        )

        extended_query = json.loads(response.text)
        return extended_query

    except Exception as e:
        print(f"LLM 최적화 실패: {e}")
        return {
            "final_query": user_query,
        }
