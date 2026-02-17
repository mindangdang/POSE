# 수정할 상단 Import 부분
import os
import json
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from io import BytesIO
from pydantic import BaseModel, Field
from typing import List, Optional

# ---------------------------------------------------------
# 1. 환경변수 및 API 설정
# ---------------------------------------------------------

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("⚠️ .env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")
genai.configure(api_key=api_key)

# ---------------------------------------------------------
# 2.schema에 대한 Pydantic
# ---------------------------------------------------------

class Facts(BaseModel):
    title: Optional[str] = Field(description="상품명, 브랜드명, 작품명, 상호명 또는 주제, 제목")
    price_info: Optional[str] = Field(description="상품가격, 메뉴 가격대 등 비용 관련 텍스트")
    location_text: Optional[str] = Field(description="위치, 주소 텍스트")
    time_info: Optional[str] = Field(description="시간/기간 텍스트")
    key_details: Optional[List[str]] = Field(description="핵심 특징 1, 2, 3")

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

def extract_fact_and_vibe(image_path: str, caption: str, hashtags: list):
    print(f"\n⚡ [Gemini 2.5 Flash] '{image_path}'와 텍스트를 통합 분석 중입니다...")

    # 안전하게 다운로드된 로컬 이미지 열기
    img = Image.open(image_path)

    # 해시태그 통합
    tags_str = " ".join(hashtags) if hashtags else ""
    text_input = f"캡션: {caption}\n해시태그: {tags_str}"

    prompt = """
    너는 인스타그램 게시물을 분석하여 '취향 검색 DB용' 데이터를 추출하는 AI야.
    제공된 '이미지'와 '텍스트(캡션+해시태그)'를 종합적으로 분석해줘.

    [핵심 분석 지시사항]
    1. 대상 식별: 게시물이 소개하는 장소, 상품, 정보 등 핵심 대상을 모두 찾아내. (1개일 수도, 여러 개일 수도 있음)
    2. 시각 정보 분석 (Vision & OCR): 이미지 속 글자(간판, 메뉴, 로고, 자막 등)를 꼼꼼히 읽고, 사진의 전반적인 분위기(조명, 색감, 인테리어, 스타일)를 파악해 텍스트의 맥락과 결합해.
    3. 객관적 팩트 (Facts): 확인 가능한 사실(이름, 위치, 가격, 시간, 특징)만 정확히 추출해. 본문에 없거나 유추할 수 없는 정보는 절대 지어내지 말고 비워둬(null).
    4. 주관적 감성 (Vibe): 객관적 팩트를 제외한 '감성, 분위기, 방문/사용 맥락'을 요약해. 사용자가 "비오는 날 조용한 곳", "힙한 스트릿 룩"처럼 검색할 때 매칭될 수 있도록, '느좋', '차분한', '퇴폐적인' 같은 추상적 키워드를 문장에 풍부하게 녹여내.
    5. 카테고리 분류: 각 대상의 성격을 PLACE, PRODUCT, CONTENT, EVENT, TIP, INSPIRATION 중 하나로 정확히 판별해.
        """

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": InstaAnalysisResult, 
            "temperature": 0.2 
        }
    )
    
    response = model.generate_content([prompt, img, text_input])
    return json.loads(response.text)
