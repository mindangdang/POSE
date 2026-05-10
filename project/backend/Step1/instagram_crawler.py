import logging
import re
import os
import uuid
import asyncio
import random
import mimetypes
from urllib.parse import urlparse

import httpx
from typing import Dict, List, Optional
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async

logger = logging.getLogger(__name__)

HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")
VIDEO_SELECTOR = "video"
NEXT_BUTTON_SELECTOR = "button[aria-label*='Next'], button[aria-label*='다음']"

CAPTION_CONTAINER_SELECTOR = "article ul li"


class InstagramAccountPool:
    """간단한 세션/쿠키 로테이션 풀."""

    def __init__(self, accounts: Optional[List[Dict[str, object]]] = None, cooldown_sec: int = 900):
        self.accounts = accounts or []
        self.cooldown_sec = cooldown_sec

    def get_available_account(self) -> Optional[Dict[str, object]]:
        now = asyncio.get_event_loop().time()
        for account in self.accounts:
            blocked_until = account.get("blocked_until", 0)
            if blocked_until <= now:
                return account
        return None

    def mark_temporary_block(self, account_id: str):
        now = asyncio.get_event_loop().time()
        for account in self.accounts:
            if account.get("id") == account_id:
                account["blocked_until"] = now + self.cooldown_sec
                break


async def human_delay(mu: float = 1.8, sigma: float = 0.9, min_sec: float = 0.3, max_sec: float = 5.0):
    delay = max(min_sec, min(max_sec, random.gauss(mu, sigma)))
    await asyncio.sleep(delay)


async def apply_stealth(page):
    await stealth_async(page)
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """
    )


def _extract_highest_resolution_srcset(srcset: str) -> Optional[str]:
    candidates = []
    for entry in srcset.split(","):
        parts = entry.strip().split()
        if not parts:
            continue
        url = parts[0]
        size = 0
        if len(parts) > 1 and parts[1].endswith("w"):
            try:
                size = int(parts[1][:-1])
            except ValueError:
                size = 0
        candidates.append((size, url))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


async def _extract_caption_from_dom(post_container) -> str:
    caption_items = post_container.locator(CAPTION_CONTAINER_SELECTOR)
    count = await caption_items.count()
    if count == 0:
        return ""

    first_li = caption_items.nth(0)
    text_blocks = first_li.locator("span[dir='auto']")
    texts = []
    for i in range(await text_blocks.count()):
        text = (await text_blocks.nth(i).inner_text()).strip()
        if text and not text.startswith("@"):
            texts.append(text)

    return "\n".join(texts).strip()


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
        "graphql_payloads": [],
    }

    try:
        await apply_stealth(page)

        network_payloads = []

        async def handle_response(resp):
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                return
            if "graphql" in resp.url or "/api/v1/" in resp.url:
                try:
                    payload = await resp.json()
                    network_payloads.append({"url": resp.url, "payload": payload})
                except Exception:
                    return

        page.on("response", handle_response)

        await human_delay()
        await page.goto(post_url, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("article, main", timeout=15000)
        except PlaywrightTimeoutError:
            page_text = (await page.content()).lower()
            if "login" in page.url or "로그인" in page_text:
                result["requires_login"] = True
                result["error"] = "로그인이 필요하거나 쿠키가 만료되었습니다."
            else:
                result["blocked"] = True
                result["error"] = "접근이 차단되었거나 페이지 구조가 변경되었습니다."
            return result

        post_container = page.locator("article").first if await page.locator("article").count() > 0 else page.locator("main").first

        caption = await _extract_caption_from_dom(post_container)
        if caption:
            result["caption"] = caption
            result["hashtags"] = HASHTAG_PATTERN.findall(caption)

        all_images = []
        is_video = False

        for _ in range(max_slides):
            await page.wait_for_timeout(500)
            await human_delay()

            if await post_container.locator(VIDEO_SELECTOR).count() > 0:
                is_video = True

            images = await post_container.locator("img").evaluate_all(
                """elements => elements
                    .filter(e => e.clientWidth > 250)
                    .map(e => {
                        const srcset = e.getAttribute('srcset') || '';
                        return { src: e.src, srcset };
                    })
                """
            )

            for image in images:
                best = _extract_highest_resolution_srcset(image.get("srcset", "")) or image.get("src")
                if best and ("cdninstagram.com" in best or "fbcdn.net" in best):
                    all_images.append(best)

            next_btn = post_container.locator(NEXT_BUTTON_SELECTOR).first
            if await next_btn.is_visible():
                box = await next_btn.bounding_box()
                if box:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    await page.mouse.move(x + random.uniform(-5, 5), y + random.uniform(-3, 3), steps=10)
                    await human_delay(mu=0.4, sigma=0.2, min_sec=0.1, max_sec=1.2)
                    await page.mouse.down()
                    await human_delay(mu=0.25, sigma=0.1, min_sec=0.08, max_sec=0.8)
                    await page.mouse.up()
                else:
                    await next_btn.click()
                await page.wait_for_timeout(1000)
            else:
                break

        result["image_urls"] = list(dict.fromkeys(all_images))
        result["graphql_payloads"] = network_payloads

        if is_video:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except Exception as e:
        logger.exception(f"크롤링 중 예외 발생: {e}")
        result["error"] = str(e)

    return result


FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.instagram.com/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def _extension_from_content_type(content_type: str) -> str:
    mime = content_type.split(";")[0].strip().lower()
    ext = mimetypes.guess_extension(mime) or ""
    if ext in {".jpe", ".jpeg"}:
        return ".jpg"
    return ext or ".bin"


async def _download_single_image(client: httpx.AsyncClient, url: str, save_dir: str) -> Optional[str]:
    try:
        async with client.stream("GET", url, timeout=20.0) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            ext = _extension_from_content_type(content_type)

            if ext == ".bin":
                path_ext = os.path.splitext(urlparse(url).path)[1]
                ext = path_ext if path_ext else ".bin"

            file_name = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(save_dir, file_name)

            with open(file_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 64):
                    f.write(chunk)

        return file_path
    except Exception as e:
        print(f"이미지 다운로드 실패 ({url[:30]}...): {e}")
        return None


async def download_images(image_urls: list, save_dir: str = "insta_vibes") -> list:
    if not image_urls:
        return []

    os.makedirs(save_dir, exist_ok=True)

    async with httpx.AsyncClient(headers=FAKE_HEADERS, http2=True) as client:
        tasks = [_download_single_image(client, url, save_dir) for url in image_urls]
        results = await asyncio.gather(*tasks)

    return [path for path in results if path is not None]
