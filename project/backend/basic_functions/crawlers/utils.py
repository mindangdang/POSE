import os
from google import genai
from google.genai import types
from project.backend.app.schemas.response import ProductAnalysisResult
from project.backend.app.manage.settings import load_backend_env
from fastapi import WebSocket
import httpx
import uuid
import asyncio
import httpx

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


def _mark_feed_add_items(items: list[dict]) -> None:
    for item in items:
        facts = item.get("facts")
        if not isinstance(facts, dict):
            facts = {}
            item["facts"] = facts
        facts["_source"] = "feed_add"

# 단일 이미지 다운로드용 헬퍼 함수 (Non-blocking 파일 저장)
async def _download_single_image(client: httpx.AsyncClient, url: str, save_dir: str) -> str:
    try:
        response = await client.get(url, timeout=15.0, follow_redirects=True)
        response.raise_for_status()

        # 고유한 UUID 파일명 생성 (여러 요청이 겹쳐도 덮어쓰기 방지)
        file_name = f"{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(save_dir, file_name)

        # 파일 저장은 디스크 I/O이므로 서버 멈춤을 막기 위해 스레드 풀에서 실행
        def save_file():
            with open(file_path, "wb") as f:
                f.write(response.content)
                
        await asyncio.to_thread(save_file)
        return file_path
    except Exception as e:
        print(f"이미지 다운로드 실패 ({url[:30]}...): {e}")
        return None

# httpx와 asyncio.gather를 이용한 초고속 병렬 다운로드
async def download_images(image_urls: list, save_dir: str = "insta_vibes") -> list:
    if not image_urls:
        return []

    # exist_ok=True를 주면 이미 폴더가 있어도 에러가 나지 않습니다.
    os.makedirs(save_dir, exist_ok=True)

    # 모든 이미지를 동시에 병렬 다운로드
    async with httpx.AsyncClient(headers=FAKE_HEADERS, http2=True) as client:
        tasks = [_download_single_image(client, url, save_dir) for url in image_urls]
        results = await asyncio.gather(*tasks)

    # 실패한(None) 다운로드를 걸러내고 성공한 경로만 반환
    return [path for path in results if path is not None]

async def fetch_image_task(normalized_image_url,IMAGE_DIR) -> str:
    if normalized_image_url.startswith(("http://", "https://")):
        files = await download_images([normalized_image_url], str(IMAGE_DIR))
        if files:
            local_name = os.path.basename(files[0])
            print(f"[백그라운드] 외부 상품 이미지를 로컬로 저장 완료: {local_name}")
            return local_name
        print(f"[백그라운드] 이미지 다운로드 실패, 원본 URL 유지: {normalized_image_url[:120]}")
    return ""
    
async def fetch_image_task(payload,IMAGE_DIR) -> str:
    if payload.image_url and payload.image_url.startswith(("http://", "https://")):
        files = await download_images([payload.image_url], str(IMAGE_DIR))
        if files:
            return os.path.basename(files[0])
    return payload.image_url or ""
