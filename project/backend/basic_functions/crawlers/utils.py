import asyncio
import html
import uuid
from pathlib import Path
from typing import Sequence

import httpx
from google import genai
from google.genai import types

from project.backend.app.manage.resilience import with_llm_resilience
from project.backend.app.manage.settings import get_settings

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.instagram.com/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

settings = get_settings()
api_key = settings.google_api_key
if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

def _mark_feed_add_items(items: list[dict]) -> None:
    for item in items:
        facts = item.get("facts")
        if not isinstance(facts, dict):
            facts = {}
            item["facts"] = facts
        facts["_source"] = "feed_add"

def _normalize_image_url(raw_url: str | None) -> str:
    normalized_image_url = html.unescape(raw_url.strip()) if isinstance(raw_url, str) else ""
    if normalized_image_url.startswith("//"):
        normalized_image_url = f"https:{normalized_image_url}"
    return normalized_image_url


async def _download_single_image(client: httpx.AsyncClient, url: str, save_dir: Path) -> str | None:
    try:
        response = await client.get(url, timeout=15.0, follow_redirects=True)
        response.raise_for_status()

        save_dir.mkdir(parents=True, exist_ok=True)

        # 고유한 UUID 파일명 생성 (여러 요청이 겹쳐도 덮어쓰기 방지)
        file_name = f"{uuid.uuid4().hex}.jpg"
        file_path = save_dir / file_name

        # 파일 저장은 디스크 I/O이므로 서버 멈춤을 막기 위해 스레드 풀에서 실행
        def save_file():
            with file_path.open("wb") as f:
                f.write(response.content)

        await asyncio.to_thread(save_file)
        return file_name
    except Exception as e:
        print(f"이미지 다운로드 실패 ({url[:30]}...): {e}")
        return None

async def download_images(image_urls: Sequence[str], save_dir: str | Path = "insta_vibes") -> list[str]:
    if not image_urls:
        return []

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # 모든 이미지를 동시에 병렬 다운로드
    async with httpx.AsyncClient(headers=FAKE_HEADERS, http2=True) as client:
        tasks = [_download_single_image(client, url, save_path) for url in image_urls]
        results = await asyncio.gather(*tasks)

    # 실패한(None) 다운로드를 걸러내고 성공한 경로만 반환
    return [path for path in results if path is not None]

def normalize_url(raw_url) -> str:
    return _normalize_image_url(raw_url)

async def fetch_image_task(image_url, IMAGE_DIR) -> str:
    normalized_url = _normalize_image_url(image_url)
    if normalized_url.startswith(("http://", "https://")):
        files = await download_images([normalized_url], IMAGE_DIR)
        if files:
            local_name = files[0]
            print(f"[백그라운드] 외부 상품 이미지를 로컬로 저장 완료: {local_name}")
            return local_name
        print(f"[백그라운드] 이미지 다운로드 실패, 원본 URL 유지: {normalized_url[:120]}")
    return ""

