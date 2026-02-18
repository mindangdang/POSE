import os
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional

# ---------------------------------------------------------
# 1. 환경변수 및 API 설정
# ---------------------------------------------------------

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("⚠️ .env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=api_key)

# ---------------------------------------------------------
# 2. Schema에 대한 Pydantic 정의
# ---------------------------------------------------------

class Facts(BaseModel):
    title: Optional[str] = Field(description="상품명, 브랜드명, 작품명, 상호명 또는 주제, 제목", default=None)
    price_info: Optional[str] = Field(description="상품가격, 메뉴 가격대 등 비용 관련 텍스트", default=None)
    location_text: Optional[str] = Field(description="위치, 주소 텍스트", default=None)
    time_info: Optional[str] = Field(description="시간/기간 텍스트", default=None)
    key_details: Optional[List[str]] = Field(description="핵심 특징 1, 2, 3", default=None)

class ExtractedItem(BaseModel):
    category: str = Field(description="PLACE, PRODUCT, MEDIA, TIP, INSPIRATION 중 택 1")
    summary_text: str = Field(description="이 게시물이 무엇을 말하는지 객관적이고 간략한 내용 요약 (앱 화면 노출용)")
    vibe_text: str = Field(description="감성, 분위기, 사용 맥락 요약. 상황에 맞는 추상적 키워드를 문장에 자연스럽게 포함할 것 (유사도 검색용)")
    facts: Facts

class InstaAnalysisResult(BaseModel):
    extracted_items: List[ExtractedItem]

# ---------------------------------------------------------
# 3. Gemini 2.5 Flash 분석 엔진 
# ---------------------------------------------------------

def extract_fact_and_vibe(image_paths: List[str], caption: str, hashtags: list):
    print(f"\n⚡ [Gemini 2.5 Flash] '{image_paths}'와 텍스트를 통합 분석 중입니다...")

    # 안전하게 다운로드된 로컬 이미지 열기
    images = []
    for path in image_paths:
        try:
            images.append(Image.open(path))
        except Exception as e:
            print(f"⚠️ 이미지 로드 실패 ({path}): {e}")

    # 해시태그 통합
    tags_str = " ".join(hashtags) if hashtags else ""
    text_input = f"캡션: {caption}\n해시태그: {tags_str}"

    prompt = """
    너는 한장 이상의 이미지 슬라이드로 구성된 인스타그램 게시물을 분석하여 '취향 검색 DB용' 데이터를 추출해내는 세계 최고 수준의 AI 데이터 엔지니어야.
    제공된 '이미지(순서대로)'들과 '텍스트(캡션+해시태그)'를 종합적으로 분석해.

    [핵심 분석 사고 과정 (Chain of Thought)]
    1. 노이즈 필터링: 썸네일(표지)이나 마지막 인사말(아웃트로) 등 실제 정보가 없는 슬라이드는 무시해. 제공된 이미지 수와 실제 소개하는 대상(Item)의 수는 다를 수 있다는 점을 인지해.
    2. 순차적 기준점 추적 (Sequential Tracking): 첫 번째로 등장하는 유의미한 '상호명, 상품명, 또는 주제(Anchor)'를 찾아내. 그 순간부터 등장하는 모든 시각적 특징과 텍스트 설명은 해당 대상의 정보로 수집해.
    3. 교차 검증 (Cross-matching): 캡션에 적힌 설명이 몇 번째 슬라이드의 어떤 대상을 가리키는지 논리적으로 연결해. 이미지 속 글자(OCR)와 캡션의 설명을 결합해서 하나의 완벽한 대상 프로필을 완성해.
    4. 독립적 데이터 분할: 읽어나가다가 새로운 상호명/상품명(다음 Anchor)이 등장하거나, 순번(예: "2.", "두 번째는")이 바뀌면 이전 대상의 정보 수집을 즉시 종료하고 확정해. 대상 간의 정보가 절대 섞이지 않게 마지막 슬라이드까지 순차적으로 반복해.

    [데이터 추출 및 작성 규칙]
    - 객관적 팩트 (Facts): 확인 가능한 사실(이름, 위치, 가격, 시간, 특징)만 정확히 추출해. 본문에 없거나 유추할 수 없는 정보는 절대 지어내지 말고 `null`로 비워둬.
    - 주관적 감성 (Vibe): 최대한 원본자료에 있는 설명을 그대로 이용하고 단순 정보만 전달하는 정보성 게시물이라면, 억지로 지어내지 말고 `vibe_text`를 빈 문자열("")로 둬.  
    - 요약(summary text): 꼭 필요한 핵심적인 내용만을 포함해.
    - 카테고리 분류: 추출된 각 대상의 유형을 아래 5가지 중 하나로 정확히 판별해.
    * PLACE: 카페, 맛집, 팝업스토어, 전시회 등 직접 방문 가능한 '물리적 장소'
    * PRODUCT: 옷, 화장품, 전자기기 등 구매 가능한 '실물 상품'
    * MEDIA: 영화, 책, 음악, 드라마 등 감상하는 '미디어 작품'
    * TIP: 어플 사용법, 레시피, 운동법, 엑셀 단축키 등 학습이나 참고용 '정보성 글'
    * INSPIRATION: 룩북, 인테리어 무드 등 특정 대상의 팩트보다 전체적인 '스타일/느낌'을 참고하기 위한 레퍼런스
    """

    contents = [prompt] + images + [text_input]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InstaAnalysisResult,  
            temperature=0.1 
        )
    )

    return response.parsed.model_dump()