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
    category: str = Field(description="PLACE, PRODUCT, CONTENT, EVENT, TIP, INSPIRATION 중 택 1")
    summary_text: str = Field(description="이 게시물이 무엇을 말하는지 객관적이고 간략한 내용 요약 (앱 화면 노출용)")
    vibe_text: str = Field(description="감성, 분위기, 사용 맥락 요약. '느좋', '힙한' 등 추상적 키워드를 문장에 자연스럽게 포함할 것 (유사도 검색용)")
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
    너는 여러 장의 슬라이드로 구성된 인스타그램 게시물을 분석하는 AI야.
    사용자가 제공한 여러 장의 '이미지 순서'와 '캡션+해시태그'를 종합적으로 분석해.

    [핵심 분석 지시사항]
    1. 대상 식별 및 필터링: 제공된 이미지 수와 실제 소개하는 대상(Item)의 수는 다를 수 있어. 썸네일(표지)이나 마지막 인사말(아웃트로) 슬라이드는 무시하고, '실제로 소개/리뷰하는 핵심 대상'이 총 몇 개인지 파악해.
    2. 교차 검증 (Cross-matching): 캡션에 적힌 설명이 몇 번째 슬라이드의 어떤 대상을 가리키는지 논리적으로 연결해. 이미지 속 OCR 텍스트와 캡션의 설명을 결합해서 하나의 완벽한 대상 프로필을 완성해.
    3. 객관적 팩트 (Facts): 확인 가능한 사실만 정확히 추출해. (지어내기 절대 금지, 모르면 null)
    4. 주관적 감성 (Vibe): 객관적 정보만 전달하는 밋밋한 정보성 게시물이거나 감성을 도출할 수 없다면, 억지로 지어내지 말고 `vibe_text`를 빈 문자열("")이나 null로 비워둬. 감성이 느껴질 때만 검색 최적화 키워드(예: '느좋', '차분한')를 넣어 작성해.
    5. 카테고리 분류: 추출된 각 대상의 성격을 PLACE, PRODUCT, CONTENT, EVENT, TIP, INSPIRATION 중 하나로 정확히 판별해.
    """

    # 4. 프롬프트 + 이미지 여러 장 + 텍스트를 하나의 리스트로 묶어서 전달
    contents = [prompt] + images + [text_input]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InstaAnalysisResult,  
            temperature=0.1 # 매칭의 정확도를 극대화하기 위해 온도를 더 낮춤
        )
    )

    return response.parsed.model_dump()