import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import re
from project.backend.app.core.settings import load_backend_env
from project.backend.app.core.resilience import with_llm_resilience

class ProductAnalysisResult(BaseModel):
    recommend: str = Field(description="어떤 사람에게 추천하는지 설명+대상에 대한 큐레이팅")
    key_details: List[str] = Field(description="핵심 특징 1, 2, 3")
    sub_category: Optional[str] = Field(description="아우터,자켓,상의,하의,주얼리,액세서리 중 1택", default=None)
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

@with_llm_resilience(fallback_default=lambda description: {
    "recommend": "", 
    "key_details": description[:100].strip() + "..." if len(description) > 100 else description,
    "sub_category": "미분류",
})
async def analyze_description_with_gemini(description: str) -> dict:
    if not description or description == "No description available":
        return {"recommend": "", "key_details": "", "sub_category": "미분류"}

    prompt = f"""
    다음 상품설명을 분석하여 'recommend'와'key_details','sub_category'로 분리해.

    [상품 설명]
    {description} """

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
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
        "key_details": data.key_details,
        "sub_category": data.sub_category
    }
