import asyncio
import html
import json

from fastapi import FastAPI
from project.backend.basic_functions.crawlers.shopping_crawler import scrape_product_metadata
from project.backend.basic_functions.crawlers.utils import _mark_feed_add_items, fetch_image_task, parse_description_task
from project.backend.app.db.insert_DB import insert_items_to_db
from project.backend.app.manage.settings import IMAGE_DIR
from project.backend.app.repositories import get_repositories

async def background_crawl_and_save(
    app: FastAPI,
    item_id: int,
    user_id: str,
    post_url: str,
):
    print(f"[백그라운드] 작업 시작: {post_url} (임시 ID: {item_id})")
    manager = getattr(app.state, "websocket_manager", None)

    try:
        extracted_items = []
        extracted_items = await _extract_product_items(post_url)

        if not extracted_items:
            raise RuntimeError("아이템 정보를 추출하지 못했습니다.")

        _mark_feed_add_items(extracted_items)

        async with app.state.db_pool.connection() as conn:
            repos = get_repositories(conn)
            await repos.saved_posts.delete_by_id(item_id, user_id)
            await insert_items_to_db(user_id, post_url, extracted_items, conn=conn)
            await conn.commit()
            print("[백그라운드] 작업 및 DB 저장 완료")

            # 저장된 최신 아이템 정보를 다시 조회하여 클라이언트에 전송
            all_items = await repos.saved_posts.list_feed_items(user_id)
            new_items = [item for item in all_items if item.get("url") == post_url or item.get("source_url") == post_url]
            if not new_items:
                print("[백그라운드] DB에서 새 아이템을 찾을 수 없습니다.")

        if manager:
            payload = {
                "type": "CRAWL_SUCCESS",
                "placeholder_id": item_id,
                "items": new_items,
            }
            await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
            print("[백그라운드] 웹소켓 메시지 전송 완료")

    except Exception as exc:
        print(f"[백그라운드] 전체 프로세스 에러: {exc}")

        try:
            async with app.state.db_pool.connection() as conn:
                repos = get_repositories(conn)
                await repos.saved_posts.delete_by_id(item_id,user_id)
                await conn.commit()
                print(f"[백그라운드] 에러로 인해 임시 아이템({item_id}) 삭제 완료")

        except Exception as db_exc:
            print(f"[백그라운드] 임시 아이템({item_id}) 삭제 실패: {db_exc}")

        if manager:
            payload = {
                "type": "CRAWL_ERROR",
                "placeholder_id": item_id,
                "message": "데이터를 가져오는 데 실패했습니다. 잠시 후 다시 시도해주세요.",
            }
            await manager.broadcast_to_user(user_id, json.dumps(payload))

###################################################################################################

async def _extract_product_items(post_url: str) -> list[dict]:
    data = await scrape_product_metadata(post_url)
    if not data or data.get("title") == "추출 실패":
        print("[백그라운드] 웹페이지 정보를 가져올 수 없습니다.")
        return []

    raw_image_url = data.get("image_url", "")
    normalized_image_url = html.unescape(raw_image_url.strip()) if isinstance(raw_image_url, str) else ""
    if normalized_image_url.startswith("//"):
        normalized_image_url = f"https:{normalized_image_url}"

    local_image_url, ai_parsed_data = await asyncio.gather(
        fetch_image_task(normalized_image_url, IMAGE_DIR),
        parse_description_task(data)
    )

    ai_parsed_data = ai_parsed_data or {}

    brand_info = data.get("brand", "")
    clean_title = ai_parsed_data.get("title", "")
    final_key_details = ai_parsed_data.get("key_details", "")
    
    if brand_info:
        final_key_details = f"[{brand_info}] {final_key_details}".strip()

    return [
        {
            "title": clean_title or data.get("title", "Unknown"),
            "price": f"{data.get('price', '')} {data.get('currency', '')}".strip() or None,
            "brand": data.get("brand", ""),
            "category": ,
            "is_available": data.get("is_available", "알 수 없음"),
            "image_url": normalized_image_url,
            "shop": data.get("source", "unknown"),
        }
    ]
