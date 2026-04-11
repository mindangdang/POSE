import os
import json
from typing import List, Optional
from PIL import Image
import asyncio
from pydantic import BaseModel, Field
from project.backend.app.core.settings import load_backend_env

# 제미나이 SDK
from google import genai
from google.genai import types


# ---------------------------------------------------------
# 1. 환경변수 및 API, AI 모델 설정
# ---------------------------------------------------------

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
    image_index: int = Field(description="이 대상이 가장 잘 나타난 슬라이드의 인덱스 (첫 번째 사진은 0)") 
    category: str = Field(description="PLACE, PRODUCT, MEDIA, TIP, INSPIRATION 중 택 1")
    summary_text: str = Field(description="해당 사진이 무엇을 말하는지 객관적이고 간략한 내용 요약")
    recommend: str = Field(description="어떤 사람에게 추천하는지 설명")
    facts: Facts

class InstaAnalysisResult(BaseModel):
    extracted_items: List[ExtractedItem]

# ---------------------------------------------------------
# 3. Gemini 분석 엔진 & 멀티모달 파이프라인
# ---------------------------------------------------------

async def extract_fact_and_vibe(image_paths: List[str], caption: str, hashtags: list):
    def load_images():
        loaded_imgs = []
        for path in image_paths:
            try:
                # Image.open은 lazy load지만, API로 넘길 때를 대비해 안전하게 처리
                loaded_imgs.append(Image.open(path))
            except Exception as e:
                print(f"이미지 로드 실패 ({path}): {e}")
        return loaded_imgs
    
    images = await asyncio.to_thread(load_images)

    # 해시태그 통합
    tags_str = " ".join(hashtags) if hashtags else ""
    text_input = f"캡션: {caption}\n해시태그: {tags_str}"

    # Step.1: LLM OCR & Context Extraction
    prompt_ocr =  """
    인스타그램 게시물(이미지+텍스트)을 분석해 '취향 검색 DB'용 데이터를 추출하라.

    [핵심 분석 사고 과정 (Chain of Thought)]
    1. 노이즈 필터링: 무의미한 슬라이드(썸네일, 아웃트로 등) 무시. 제공된 이미지 수와 추출할 객체(Item)의 수는 다를 수 있음을 인지할 것.
    2. 독립적 분할: 새로운 대상(상호, 상품명, 순번) 등장 시 즉시 이전 대상과 분리하여 추출. 정보 혼합 엄금.
    3. 교차 검증: 캡션에 적힌 설명이 몇 번째 슬라이드의 어떤 대상을 가리키는지 논리적으로 연결해. 이미지 속 글자(OCR)와 캡션의 설명을 결합해서 하나의 완벽한 대상 프로필을 완성해.
    4. 독립적 데이터 분할: 읽어나가다가 새로운 상호명/상품명(다음 Anchor)이 등장하거나, 순번(예: "2.", "두 번째는")이 바뀌면 이전 대상의 정보 수집을 즉시 종료하고 확정해. 대상 간의 정보가 절대 섞이지 않게 마지막 슬라이드까지 순차적으로 반복해.
    5. 식별자: 각 독립된 대상에 고유 인덱스 번호 부여.
    6. 이미지 속에 대상을 가리키는 글이 없다면 캡션을 참고.

    [데이터 추출 및 작성 규칙]
    - Facts: 명시된 객관적 사실만 추출. 추측 절대 금지 (모르면 null).
    - recommend: 어떤 아이템을 원하는 유저에게 추천하는지 설명할 것. 
    - summary: 핵심만 요약.
    - Category (택1): PLACE(물리적 장소), PRODUCT(실물상품), MEDIA(감상용 작품), TIP(정보/팁), INSPIRATION(스타일/무드 레퍼런스)
    """

    contents = [prompt_ocr] + images + [text_input]

    response_ocr = await client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InstaAnalysisResult,  
            temperature=0.1 
        )
    )

    extracted_data = response_ocr.parsed
 
    print("모든 데이터 추출, 임베딩 및 조립 완료!")
    return extracted_data.model_dump()
