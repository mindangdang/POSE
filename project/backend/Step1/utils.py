import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import re
from project.backend.config import load_backend_env

class ProductAnalysisResult(BaseModel):
    vibe_text: str = Field(description="상품이 주는 감성, 무드, 분위기")
    key_details: List[str] = Field(description="상품의 핵심 특징 리스트")

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

async def analyze_description_with_gemini(description: str) -> dict:
    if not description or description == "No description available":
        return {"vibe_text": "No description available", "key_details": ""}

    prompt = f"""
    다음 상품설명을 분석하여 'vibe_text'와'key_details'로 분리해.
    반드시 아래 JSON 형식으로만 반환해. 마크다운 기호 없이 순수 JSON만 출력해.
    
    - vibe_text: 상품이 주는 감성, 무드, 분위기를 묘사하는 1~2문장
    - key_details: 상품의 핵심 스펙, 소재, 핏 등 객관적인 특징 요약

    [상품 설명]
    {description}

    [출력 형식]
    {{
        "vibe_text": "단순한 객관적 묘사가 아닌 아이템이 사용자의 욕구를 자극한 바로 그 '미세한 매력 포인트를 추론해 낼 것.(추론에 시 항상 근거를 생각해 검증할 것)
        "key_details": "핵심 특징"
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
        }
