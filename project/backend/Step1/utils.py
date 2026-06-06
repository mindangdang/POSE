import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
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
    sub_category: Optional[str] = Field(description="Choose 1 from Outerwear, Jacket, Top, Bottom, Jewelry, Accessories, or Shoes", default=None)

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

GPU_SERVER_URL = os.environ.get("GPU_SERVER_URL")
if not GPU_SERVER_URL:
    raise ValueError(".env 파일에 GPU_SERVER_URL이 설정되지 않았습니다.")

@with_llm_resilience(fallback_default=lambda description: {
    "recommend": "", 
    "key_details": description[:100].strip() + "..." if len(description) > 100 else description,
    "sub_category": "미분류",
})
async def analyze_description_with_gemini(description: str) -> dict:
    if not description or description == "No description available":
        return {"title": "", "recommend": "", "price": "", "key_details": "", "sub_category": "미분류"}

    prompt = f"""
    다음 상품정보를 분석하여 'title', 'recommend', 'price' 'key_details', 'sub_category'로 분리해.
    *참고: 아우터는 패딩,코트 같은 종류고, 자켓은 블루종,가죽자켓 같은 종류야.

    [상품 정보]
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
        "sub_category": data.sub_category,
        "title": data.title,
        "price": data.price
    }

domain_map = {
        "musinsa.com": "무신사",
        "m.bunjang.co.kr" : "번개장터",
        "fruitsfamily.com": "후루츠패밀리",
        "zara.com": "자라",
        "instagram.com": "인스타그램"
    }

async def fetch_from_single_site(
    client: httpx.AsyncClient, 
    query: str, 
    domain: str, 
    site_name: str, 
    current_page: int, 
    serp_api_key: str, 
    params: Optional[dict] = None
) -> list[dict]:
    if params is None:
        params = {
            "engine": "google",
            "q": query,
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
        data = response.json()
        
        # Google Images는 'images_results', Google Lens는 'visual_matches'를 사용함
        items = data.get("images_results") or data.get("visual_matches") or []
        print(f"[{site_name or 'SerpApi'}] 검색 성공: {len(items)}개")
        
        results = []
        for item in items:
            # 이미지 URL 추출 로직 통합
            image_url = item.get("thumbnail", "")
            if "original" in item and "instagram" not in domain:
                image_url = item.get("original") or image_url
            
            # 가격 정보 추출 (Lens는 dict 형태일 수 있음)
            price = item.get("price")
            if isinstance(price, dict):
                price = price.get("value")
            price = price or item.get("snippet") or "가격 미상"
            
            shop = item.get("source") or site_name or "알 수 없는 샵"

            results.append({
                "id": str(uuid.uuid4()),
                "category": "PRODUCT",
                "sub_category": query if not query.startswith("http") else "PRODUCT",
                "recommend": f"{shop}에서 발견한 아이템",
                "image_url": image_url,
                "url": item.get("link", ""),
                "facts": {
                    "title": item.get("title", "상품명 없음"),
                    "Price": price,
                    "Shop": shop,
                },
            })
        return results

    except Exception as e:
        print(f"[{domain}] 검색 실패: {e}")
        return []
