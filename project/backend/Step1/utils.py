import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import re

# 1. 인스타 코드와 동일한 구조의 스키마 정의
class Review(BaseModel):
    star_review: str = Field(description="별점 등 해당 대상에 대한 평균적인 점수 정보", default="")
    core_summary: str = Field(description="여러사람들의 리뷰를 중요하고 핵심적인 내용만 요약한 텍스트", default="")

class ProductAnalysisResult(BaseModel):
    vibe_text: str = Field(description="상품이 주는 감성, 무드, 분위기")
    key_details: List[str] = Field(description="상품의 핵심 특징 리스트")
    reviews: Optional[Review] = None

load_dotenv()
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

async def analyze_description_with_gemini(title: str, description: str) -> dict:
    if not description or description == "No description available":
        return {"vibe_text": "No description available", "key_details": "", "reviews": {"star_review": "", "core_summary": ""}}

    prompt = f"""
    다음 상품설명을 분석하여 'vibe_text'와'key_details'로 분리하고, title을 이용해서 상품의 주요리뷰를 요약해와. 
    반드시 아래 JSON 형식으로만 반환해. 마크다운 기호 없이 순수 JSON만 출력해.
    
    - vibe_text: 상품이 주는 감성, 무드, 분위기를 묘사하는 1~2문장
    - key_details: 상품의 핵심 스펙, 소재, 핏 등 객관적인 특징 요약
    - review: 구글 검색을 통해 객관적인 평가와 유용한 리뷰 정보를 요약할 것.

    [상품명]
    {title}

    [상품 설명]
    {description}

    [출력 형식]
    {{
        "vibe_text": "무드 텍스트",
        "key_details": "핵심 특징"
        "reviews": {{
            "star_review": "4.5/5",
            "core_summary": "실제 유저들의 주요 리뷰 요약"
        }}
    }}
    """
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt, 
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],  
                temperature=0.1 
            )
        )

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
        
    except Exception as e:
        print(f"Gemini API 에러: {e}")
        # 실패 시에도 통일된 스키마 구조의 기본값 반환
        return {
            "vibe_text": description[:50] + "...", 
            "key_details": ["세부 정보 없음"],
            "reviews": {"star_review": "", "core_summary": "리뷰 정보 없음"}
        }