import logging
import re
import os
import uuid
import asyncio
import httpx
from typing import Dict
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# --- 정규식 및 선택자 ---
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")
VIDEO_SELECTOR = "video"
NEXT_BUTTON_SELECTOR = "button[aria-label*='Next'], button[aria-label*='다음'], div[role='button'] svg[aria-label='다음']"

CAPTION_CANDIDATES = [
    "h1",
    "div._a9zs", 
    "span[dir='auto']",
    "span._ap3a",
]

async def crawl_instagram_post(page, post_url: str, max_slides: int = 10) -> Dict[str, object]:
    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "post_type": "image",
        "error": None,
        "blocked": False,
        "requires_login": False,
    }

    try:
        # 페이지 이동 및 로드 대기
        await page.goto(post_url, wait_until="domcontentloaded")
        
        try:
            # article이나 main 태그가 뜰 때까지 대기
            await page.wait_for_selector("article, main", timeout=15000)
        except PlaywrightTimeoutError:
            page_text = await page.content()
            page_text = page_text.lower()
            if "login" in page.url or "로그인" in page_text:
                result["requires_login"] = True
                result["error"] = "로그인이 필요하거나 쿠키가 만료되었습니다."
            else:
                result["blocked"] = True
                result["error"] = "접근이 차단되었거나 페이지 구조가 변경되었습니다."
            return result

        # 컨테이너 설정
        if await page.locator("article").count() > 0:
            post_container = page.locator("article").first
        else:
            post_container = page.locator("main").first

        # 1. 본문(Caption) 및 해시태그 추출
        for selector in CAPTION_CANDIDATES:
            elements = await post_container.locator(selector).all()
            for element in elements:
                if await element.is_visible():
                    text = await element.inner_text()
                    text = text.strip()
                    # 아이디가 아닌 '진짜 본문(15자 이상)'인지 검증
                    if text and not text.startswith("#") and len(text) > 15:
                        result["caption"] = text
                        result["hashtags"] = HASHTAG_PATTERN.findall(text)
                        break
            if result["caption"]:
                break

        # 2. 미디어(이미지/비디오) 추출
        all_images = []
        is_video = False

        for _ in range(max_slides):
            # 화면이 로드되고 슬라이드가 넘어갈 시간을 잠깐 줌
            await page.wait_for_timeout(500)
            
            # 비디오 여부 체크
            if await post_container.locator(VIDEO_SELECTOR).count() > 0:
                is_video = True
            
            images = await post_container.locator("img").evaluate_all(
                """elements => elements
                    .filter(e => e.closest('a') === null)
                    .filter(e => e.clientWidth > 250)
                    .map(e => e.src)
                """
            )
            
            for src in images:
                if not src: continue
                if "cdninstagram.com" in src or "fbcdn.net" in src:
                    all_images.append(src)

            # 다음 슬라이드 버튼 찾기 및 클릭
            next_btn = post_container.locator(NEXT_BUTTON_SELECTOR).first
            if await next_btn.is_visible():
                await next_btn.click()
                await page.wait_for_timeout(1000) # 슬라이드 애니메이션 대기
            else:
                break

        # 중복된 이미지 URL 제거 (순서는 그대로 유지)
        result["image_urls"] = list(dict.fromkeys(all_images))

        # 게시물 타입 판별
        if is_video:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except Exception as e:
        logger.exception(f"크롤링 중 예외 발생: {e}")
        result["error"] = str(e)

    return result

# 단일 이미지 다운로드용 헬퍼 함수 (Non-blocking 파일 저장)
async def _download_single_image(client: httpx.AsyncClient, url: str, save_dir: str) -> str:
    try:
        response = await client.get(url, timeout=10.0)
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
    async with httpx.AsyncClient() as client:
        tasks = [_download_single_image(client, url, save_dir) for url in image_urls]
        results = await asyncio.gather(*tasks)

    # 실패한(None) 다운로드를 걸러내고 성공한 경로만 반환
    return [path for path in results if path is not None]