import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
import asyncio
from project.backend.app.core.settings import load_backend_env
from project.backend.app.core.resilience import with_llm_resilience
from fastapi import WebSocket
import httpx
import uuid




class ConnectionManager:
    def __init__(self):
        # 유저 ID별로 '여러 개'의 활성 웹소켓 연결(배열)을 관리합니다. (Strict Mode 대응)
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        # 해당 유저의 특정 웹소켓만 찾아 배열에서 안전하게 제거
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            # 남은 커넥션이 하나도 없으면 딕셔너리에서 키 삭제
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: str):
        if user_id in self.active_connections:
            dead_sockets = []
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead_sockets.append(ws)
            for dead_ws in dead_sockets:
                self.disconnect(dead_ws, user_id)

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
})
async def analyze_description_with_gemini(description: str) -> dict:
    if not description or description == "No description available":
        return {"recommend": "", "key_details": "", "sub_category": ""}

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

domain_map = {
        "musinsa.com": "무신사",
        "m.bunjang.co.kr" : "번개장터",
        "fruitsfamily.com": "후루츠패밀리",
        "zara.com": "자라",
        "instagram.com": "인스타그램"
    }

async def fetch_from_single_site(client: httpx.AsyncClient, base_query: str, domain: str, site_name: str, current_page: int, serp_api_key: str) -> list[dict]:
    product_hierarchy_query = "(> products)"
    exclude_list_pages = "-inurl:search -inurl:category -inurl:snap"
    final_query = f"{base_query} site:{domain} {product_hierarchy_query} {exclude_list_pages}"
    
    params = {
        "engine": "google",
        "q": final_query,
        "api_key": serp_api_key,
        "num": 5, 
        "tbm": "isch",
        "start": (current_page - 1) * 5,
        "gl": "kr",
        "hl": "ko"
    }
    
    try:
        response = await client.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        items = response.json().get("images_results", [])
        print(f"[{site_name}] 검색 성공")
        
        return [{
            "id": str(uuid.uuid4()),
            "category": "PRODUCT",
            "sub_category": "PRODUCT",
            "recommend": f"{site_name}에서 발견한 아이템",
            "image_url": item.get("thumbnail", "") if "instagram" in domain else (item.get("original", "") or item.get("thumbnail", "")),
            "url": item.get("link", ""),
            "summary_text": item.get("title", "상품명 없음"),
            "facts": {
                "title": item.get("title", "상품명 없음"),
                "Price": item.get("price") or item.get("snippet") or "가격 미상",
                "Shop": site_name,
            },
        } for item in items]

    except Exception as e:
        print(f"[{domain}] 검색 실패: {e}")
        return []