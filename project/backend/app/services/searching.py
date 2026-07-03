import asyncio
import json
import httpx
from project.backend.basic_functions.searching.utils import *

async def process_single_item(user_id, current_page, manager, model_semaphore, item: dict):
    try:
        target_url = item.get("image_url")
        if not target_url:
            return
            
        async with model_semaphore:
            if manager:
                payload = {
                    "type": "SEARCH_SUCCESS",
                    "results": [item],
                    "is_append": True,
                    "page": current_page
                }
                await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
                item_title = item.get("title")
                print(f"[DEBUG] [{item_title}] (Page: {current_page}) 프론트로 전송 완료.")

    except Exception as e:
        print(f"개별 아이템 전송 에러: {e}")

async def process_site(user_id, manager, model_semaphore, serp_api_key, current_page,query: str, domain: str, name: str, client: httpx.AsyncClient):
    try:
        product_hierarchy_query = "(> products)"
        exclude_list_pages = "-inurl:search -inurl:category -inurl:snap"
        final_query = f"{query} site:{domain} {product_hierarchy_query} {exclude_list_pages}"
        site_items = await fetch_from_single_site(client, final_query, domain, name, current_page, serp_api_key)
        ijn_val = (current_page - 1) // 3
        print(f"[DEBUG] '{name}' ({domain}) UI Page:{current_page} -> API ijn:{ijn_val} 결과:{len(site_items)}개")
        tasks = [asyncio.create_task(process_single_item(user_id, current_page, manager, model_semaphore, item)) for item in (site_items or [])]
        await asyncio.gather(*tasks, return_exceptions=True)
            
    except Exception as e:
        print(f"쇼핑몰 검색 스트리밍 처리 에러 ({domain}): {e}")