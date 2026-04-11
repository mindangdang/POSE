import asyncio
import html
import os
import uuid
from typing import Optional

from fastapi import FastAPI
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from project.backend.Step1.Rapid_api_crawler import Rapid_crawler
from project.backend.Step1.instagram_crawler import crawl_instagram_post, download_images
from project.backend.Step1.shopping_crawler import scrape_product_metadata
from project.backend.Step1.utils import analyze_description_with_gemini
from project.backend.Step2.image_ocr_llm import extract_fact_and_vibe
from project.backend.Step2.insert_DB import insert_items_to_db
from project.backend.app.core.settings import IMAGE_DIR
from project.backend.app.repositories import get_repositories


DEFAULT_USER_ID = "1"


async def background_crawl_and_save(
    app: FastAPI,
    item_id: int,
    user_id: str,
    post_url: str,
    session_id: Optional[str],
    rapid_api_key: Optional[str],
):
    print(f"[백그라운드] 작업 시작: {post_url}")
    try:
        extracted_items = []
        is_instagram = "instagram.com" in post_url.lower()

        if is_instagram:
            crawl_result = await _crawl_instagram_post(post_url, session_id, rapid_api_key)
            if not crawl_result or crawl_result.get("error"):
                error_message = crawl_result.get("error") if crawl_result else "크롤링 결과 없음"
                print(f"[백그라운드] 크롤링 실패: {error_message}")
                return

            extracted_items = await _extract_instagram_items(crawl_result)
        else:
            extracted_items = await _extract_product_items(post_url)

        if not extracted_items:
            raise RuntimeError("추출된 데이터가 없습니다.")

        async with app.state.db_pool.connection() as conn:
            repos = get_repositories(conn)
            await repos.saved_posts.delete_by_id(item_id)

            await insert_items_to_db(user_id, post_url, extracted_items, conn=conn)
            await conn.commit()
            print("[백그라운드] 작업 및 DB 저장 완료")
    except Exception as exc:
        print(f"[백그라운드] 전체 프로세스 에러: {exc}")


async def _crawl_instagram_post(
    post_url: str,
    session_id: Optional[str],
    rapid_api_key: Optional[str],
):
    if rapid_api_key:
        return await Rapid_crawler(post_url)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            if session_id:
                await context.add_cookies(
                    [
                        {
                            "name": "sessionid",
                            "value": session_id,
                            "domain": ".instagram.com",
                            "path": "/",
                            "httpOnly": True,
                            "secure": True,
                        }
                    ]
                )
            page = await context.new_page()
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            crawl_result = await crawl_instagram_post(page, post_url)
            return crawl_result
        finally:
            await browser.close()



async def _extract_instagram_items(crawl_result: dict) -> list[dict]:
    raw_downloaded_files = await download_images(crawl_result.get("image_urls", []), str(IMAGE_DIR))
    downloaded_files = []

    for old_path in raw_downloaded_files:
        if os.path.exists(old_path):
            ext = os.path.splitext(old_path)[1] or ".jpg"
            new_filename = f"{uuid.uuid4().hex}{ext}"
            new_path = str(IMAGE_DIR / new_filename)
            os.rename(old_path, new_path)
            downloaded_files.append(new_path)

    ai_result = await extract_fact_and_vibe(
    downloaded_files,
    crawl_result.get("caption", ""),
    crawl_result.get("hashtags", []),
    )
    extracted_items = ai_result.get("extracted_items", [])

    for item in extracted_items:
        image_index = int(item.get("image_index", 0) or 0)
        image_path = downloaded_files[image_index] if image_index < len(downloaded_files) else None
        item["image_url"] = os.path.basename(image_path) if image_path else ""

    return extracted_items


async def _extract_product_items(post_url: str) -> list[dict]:
    data = await scrape_product_metadata(post_url)
    if not data or data.get("title") == "추출 실패":
        print("[백그라운드] 웹페이지 정보를 가져올 수 없습니다.")
        return []

    #URL 정규화
    raw_image_url = data.get("image_url", "")
    normalized_image_url = html.unescape(raw_image_url.strip()) if isinstance(raw_image_url, str) else ""
    if normalized_image_url.startswith("//"):
        normalized_image_url = f"https:{normalized_image_url}"

    async def fetch_image_task() -> str:
        if normalized_image_url.startswith(("http://", "https://")):
            files = await download_images([normalized_image_url], str(IMAGE_DIR))
            if files:
                local_name = os.path.basename(files[0])
                print(f"[백그라운드] 외부 상품 이미지를 로컬로 저장 완료: {local_name}")
                return local_name
            print(f"[백그라운드] 이미지 다운로드 실패, 원본 URL 유지: {normalized_image_url[:120]}")
        return ""
    
    async def parse_description_task() -> dict:
        desc = data.get("description", "").strip()        
        if not desc or len(desc) < 10 or desc.lower() == "no description available":
            return {"recommend": "", "key_details": ""}
            
        return await analyze_description_with_gemini(desc)

    local_image_url, ai_parsed_data = await asyncio.gather(
        fetch_image_task(),
        parse_description_task()
    )

    ai_parsed_data = ai_parsed_data or {}

    brand_info = data.get("brand", "")
    final_key_details = ai_parsed_data.get("key_details", "")
    if brand_info:
        final_key_details = f"[{brand_info}] {final_key_details}".strip()

    return [
        {
            "category": "PRODUCT",
            "title": data.get("title", "Unknown"),
            "recommend": ai_parsed_data.get("recommend", ""),
            "image_url": local_image_url or normalized_image_url,
            "facts": {
                "title": data.get("title", ""),
                "price_info": f"{data.get('price', '')} {data.get('currency', '')}".strip(),
                "location_text": data.get("source", ""),
                "key_details": final_key_details,
            },
        }
    ]
