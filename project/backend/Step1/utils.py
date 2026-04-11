import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import re
from project.backend.app.core.settings import load_backend_env

class ProductAnalysisResult(BaseModel):
    recommend: str = Field(description="어떤 아이템을 원하는 유저에게 추천하는지 설명하는 내용")
    key_details: List[str] = Field(description="상품의 핵심 스펙, 소재, 핏 등 객관적인 특징 요약")

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
        return {"recommend": "", "key_details": ""}

    prompt = f"""
    다음 상품설명을 분석하여 'recommend'와'key_details'로 분리해.

    [상품 설명]
    {description} """

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt, 
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductAnalysisResult, 
                temperature=0.1 
            )
        )

        data = response.parsed
        
        return {
            "recommend": data.recommend,
            "key_details": data.key_details
        }
        
    except Exception as e:
        print(f"Gemini 상품 설명 분석 에러: {e}")
        return {
            "recommend": "", 
            "key_details": description[:100].strip() + "..." if len(description) > 100 else description,
        }
