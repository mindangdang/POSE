import asyncio
import base64
import json
import os
import re
import time
import traceback
from pathlib import Path
from typing import Optional
from deep_translator import GoogleTranslator
import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from project.backend.basic_functions.utils import _extract_text_vector_sync, _extract_vector_sync
from project.backend.app.manage.settings import IMAGE_DIR, get_settings
from project.backend.app.repositories import Repositories, get_repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.services.crawling import background_crawl_and_save
from project.backend.app.services.searching import process_site
from project.backend.app.services.websocket import get_websocket_manager
from project.backend.basic_functions.ai_service.image_generate_search import generate_image_from_query
from project.backend.basic_functions.ai_service.utils import upload_generated_image
from project.backend.basic_functions.crawlers.utils import fetch_image_task, normalize_url
from project.backend.basic_functions.searching.utils import fetch_from_single_site

FAIL_IMAGE_DIR = Path("project/backend/fail_images")
FAIL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


async def start_url_extraction(
    payload: UrlAnalyzeRequest,
    app: FastAPI,
    background_tasks: BackgroundTasks,
    repos: Repositories,
    user_id: int,
):
    post_url = payload.url


    # Processing rows do not belong in the normalized saved_posts join table.
    # A negative transient ID is only used to reconcile the websocket response.
    placeholder_id = -time.time_ns()

    background_tasks.add_task(
        background_crawl_and_save,
        app,
        placeholder_id,
        user_id,
        post_url,
    )

    return {
        "success": True,
        "message": "데이터 추출 및 AI 분석이 시작되었습니다.",
        "product_id": placeholder_id,
        "data": [
            {   
                "product_id": placeholder_id,
                "title": "PROCESSING",
                "price": None,
                "brand": None,
                "category": "PROCESSING",
                "is_soldout": None,
                "image_url": "",
                "image_vector": None,
                "shop": None,
                "likes": None,
                "dislikes": None,
                "source_url": post_url,
            }
        ],
    }


async def stream_product_db_search_results(
    app: FastAPI,
    user_id: int,
    query: str,
    current_page: int,
    limit: int = 20,
): # TODO: 사이트 선택시 그 사이트의 상품만 가져오게 
    """검색어 텍스트 임베딩으로 product_db title_vector 유사 상품을 스트리밍합니다."""
    manager = get_websocket_manager(app)
    translated_query = GoogleTranslator(source='auto', target='en').translate(query)
    query_vector = await _extract_text_vector_sync(translated_query)
    if query_vector and isinstance(query_vector[0], list):
        query_vector = query_vector[0]

    if not query_vector:
        print(f"[DEBUG] product_db 검색 스킵: query='{query}' 텍스트 임베딩 실패")
        return

    pool = getattr(app.state, "db_pool", None)
    if pool is None or pool.closed:
        print("[DEBUG] product_db 검색 스킵: DB 풀이 초기화되지 않았습니다.")
        return

    conn = None
    try:
        conn = await pool.getconn()
        repos = get_repositories(conn)
        product_items = await repos.product_db.search_by_title_vector(query_vector, limit=limit)
        print(f"[DEBUG] product_db title_vector 검색 결과:{len(product_items)}개")

        if not manager:
            return

        for item in product_items:
            payload = {
                "type": "SEARCH_SUCCESS",
                "results": [item],
                "is_append": True,
                "page": current_page,
            }
            await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
    except Exception as exc:
        print(f"product_db 벡터 검색 에러: {exc}")
    finally:
        if conn is not None:
            await pool.putconn(conn)


async def search_product_db_by_title(
    app: FastAPI,
    query: str,
    limit: int = 12,
):
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []

    pool = getattr(app.state, "db_pool", None)
    if pool is None or pool.closed:
        print("[DEBUG] product_db title search skipped: DB pool is not initialized.")
        return []

    translated_query = normalized_query
    try:
        translated_query = GoogleTranslator(source='auto', target='en').translate(normalized_query) or normalized_query
    except Exception:
        translated_query = normalized_query

    conn = None
    try:
        query_vector = await _extract_text_vector_sync(translated_query)
        if query_vector and isinstance(query_vector[0], list):
            query_vector = query_vector[0]

        conn = await pool.getconn()
        repos = get_repositories(conn)

        text_matches = await repos.product_db.search_by_title_text(normalized_query, limit=limit)
        vector_matches = []
        if query_vector:
            vector_matches = await repos.product_db.search_by_title_vector(query_vector, limit=limit)

        merged: list[dict] = []
        seen_ids: set[str] = set()

        for item in text_matches + vector_matches:
            product_id = str(item.get("product_id") or "")
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            merged.append(item)
            if len(merged) >= limit:
                break

        return merged
    except Exception as exc:
        print(f"product_db title search error: {exc}")
        return []
    finally:
        if conn is not None:
            await pool.putconn(conn)


async def background_pse_search(
    app: FastAPI,
    user_id: int,
    query: str,
    page: Optional[int],
    custom_domain_map: Optional[dict] = None,
):
    manager = get_websocket_manager(app)
    serp_api_key = get_settings().serp_api_key

    if not serp_api_key:
        if manager:
            payload = {"type": "SEARCH_ERROR", "message": "SerpApi 키가 설정되지 않았습니다."}
            await manager.broadcast_to_user(user_id, json.dumps(payload))
        return

    print(f"[DEBUG] background_pse_search 시작: user_id={user_id}, query='{query}', page={page}")

    try:
        current_page = 1
        if page is not None:
            try:
                current_page = max(1, int(page))
            except (ValueError, TypeError):
                current_page = 1

        model_semaphore = asyncio.Semaphore(4)

        print("여러 쇼핑몰 병렬 검색 및 실시간 전송 시작...")
        target_domains = custom_domain_map if custom_domain_map is not None else {"google.com": "구글"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            site_tasks = [
                asyncio.create_task(
                    process_site(user_id, manager, model_semaphore, serp_api_key, current_page, query, domain, name, client)
                )
                for domain, name in target_domains.items()
            ]
            site_tasks.append(
                asyncio.create_task(
                    stream_product_db_search_results(app, user_id, query, current_page)
                )
            )
            await asyncio.gather(*site_tasks, return_exceptions=True)

        print("모든 쇼핑몰 검색 및 스트리밍 완료.")

    except Exception as exc:
        traceback.print_exc()
        if manager:
            payload = {"type": "SEARCH_ERROR", "message": f"쇼핑 검색 중 오류: {str(exc)}"}
            await manager.broadcast_to_user(user_id, json.dumps(payload))

    finally:
        if manager:
            await manager.broadcast_to_user(user_id, json.dumps({"type": "SEARCH_FINISHED"}))


def enqueue_pse_search(
    payload: SearchRequest,
    app: FastAPI,
    background_tasks: BackgroundTasks,
    user_id: str,
):
    background_tasks.add_task(
        background_pse_search,
        app,
        user_id,
        payload.query,
        payload.page,
        payload.domain_map,
    )
    return {"success": True, "message": "웹 검색 및 AI 분석이 백그라운드에서 시작되었습니다."}


async def search_with_lens(file: UploadFile | None, query: str | None):
    serp_api_key = get_settings().serp_api_key
    if not serp_api_key:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")

    search_image_url = await _resolve_lens_image_url(file=file, query=query)
    if not search_image_url:
        raise HTTPException(status_code=500, detail="이미지 검색에 사용할 URL을 생성하는 데 실패했습니다.")

    try:
        params = {
            "engine": "google_lens",
            "api_key": serp_api_key,
            "url": search_image_url,
            "hl": "ko",
            "gl": "kr",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            results = await fetch_from_single_site(
                client=client,
                query=search_image_url,
                domain="google_lens",
                site_name=None,
                current_page=1,
                serp_api_key=serp_api_key,
                params=params,
            )

        print(f" 통과한 최종결과 개수: {len(results)}")
        return {"success": True, "results": results}

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"구글 렌즈 검색 중 오류: {exc}") from exc


async def _resolve_lens_image_url(file: UploadFile | None, query: str | None) -> str | None:
    if file:
        file_content = await file.read()
        print(f"SerpApi(Google Lens)로 파일 디깅 시작: {file.filename}")
        return await upload_generated_image(file_content)

    if not query:
        raise HTTPException(status_code=400, detail="유효한 이미지 URL, 파일 또는 검색어가 필요합니다.")

    if query.startswith(("http://", "https://", "//")):
        search_image_url = query if not query.startswith("//") else f"https:{query}"
        print(f"SerpApi(Google Lens)로 URL 디깅 시작: {search_image_url}")
        return search_image_url

    if query.startswith("data:image"):
        print("SerpApi(Google Lens)로 클립보드 복사 이미지 디깅 시작")
        base64_str = re.sub(r"^data:image/.+;base64,", "", query)
        image_data = base64.b64decode(base64_str)
        return await upload_generated_image(image_data)

    print(f"SerpApi(Google Lens)로 검색어 기반 이미지 생성 및 디깅 시작: {query}")
    generated_image_bytes = await generate_image_from_query(query)
    return await upload_generated_image(generated_image_bytes)


async def save_manual_item(payload: ManualItemCreate, user_id: int, repos: Repositories):
    try:
        normalized_image_url = normalize_url(payload.image_url)
        if normalized_image_url.startswith(("http://", "https://")):
            stored_image_url = await fetch_image_task(normalized_image_url, IMAGE_DIR)
            image_url = stored_image_url or normalized_image_url
        else:
            image_url = normalized_image_url

        vector_source = image_url or normalized_image_url
        vector_list = await _extract_vector_sync(vector_source) if vector_source else None
        vector_str = str(vector_list) if vector_list else None
        
        product_id = payload.product_id
        if product_id is None or not await repos.product_db.exists(product_id):
            product_id = await repos.product_db.insert_item(
                payload.source_url or image_url or payload.title or "manual",
                {
                    "title": payload.title,
                    "price": payload.price,
                    "brand": payload.brand,
                    "category": payload.category,
                    "is_soldout": payload.is_soldout,
                    "image_url": image_url,
                    "image_vector": vector_str,
                    "shop": payload.shop,
                },
            )

        await repos.saved_posts.create(
            product_id=product_id,
            user_id=user_id,
            likes=int(payload.likes or 0),
            dislikes=int(payload.dislikes or 0),
        )
        await repos.saved_posts.conn.commit()
        return {"success": True, "message": "웹 검색 결과가 내 피드로 이동되었습니다."}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"수동 저장 실패: {exc}") from exc


async def list_items_for_user(user_id: int, repos: Repositories):
    try:
        items = await repos.saved_posts.list_feed_items(user_id)
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return items
    except Exception as exc:
        print(f"조회 에러: {exc}")
        return []


async def get_random_item_for_user(user_id: int, repos: Repositories):
    try:
        return await repos.saved_posts.get_random_feed_item(user_id)
    except Exception as exc:
        print(f"랜덤 조회 에러: {exc}")
        return None


async def vote_for_item(product_id: int, user_id: int, direction: str, repos: Repositories):
    try:
        voted_item = await repos.saved_posts.increment_vote_count(product_id, user_id, direction)
        if voted_item is None:
            raise HTTPException(status_code=404, detail="투표할 아이템을 찾을 수 없습니다.")

        await repos.saved_posts.conn.commit()
        return voted_item
    except HTTPException:
        await repos.saved_posts.conn.rollback()
        raise
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"투표 처리 실패: {exc}") from exc


async def delete_item_for_user(product_id: int, user_id: int, repos: Repositories):
    try:
        await repos.saved_posts.delete_by_id(product_id, user_id)
        await repos.saved_posts.conn.commit()
        return {"success": True}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _normalize_image_reference(image_path: str) -> Path:
    normalized = str(image_path or "").strip().replace("\\", "/")
    normalized = normalized.removeprefix("/api/images/")
    normalized = normalized.removeprefix("/images/")
    normalized = normalized.lstrip("/")
    return Path(normalized)


def resolve_image_path(filename: str) -> Path:
    relative_path = _normalize_image_reference(filename)
    normal_path = Path(IMAGE_DIR) / relative_path
    if normal_path.exists() and normal_path.is_file():
        return normal_path

    fail_path = FAIL_IMAGE_DIR / relative_path
    if fail_path.exists() and fail_path.is_file():
        return fail_path

    raise HTTPException(status_code=404, detail="Image not found")
