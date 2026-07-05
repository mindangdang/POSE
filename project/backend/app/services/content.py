import asyncio
import base64
import json
import os
import re
import traceback
from pathlib import Path
from typing import Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from project.backend.basic_functions.utils import _extract_vector_sync
from project.backend.app.manage.settings import IMAGE_DIR, get_settings
from project.backend.app.repositories import Repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.services.crawling import background_crawl_and_save
from project.backend.app.services.searching import process_site
from project.backend.app.services.websocket import get_websocket_manager
from project.backend.basic_functions.ai_service.image_generate_search import generate_image_from_query
from project.backend.basic_functions.ai_service.utils import upload_generated_image
from project.backend.basic_functions.crawlers.utils import analyze_description_with_gemini, download_images
from project.backend.basic_functions.searching.utils import domain_map, fetch_from_single_site

FAIL_IMAGE_DIR = Path("project/backend/fail_images")
FAIL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


async def start_url_extraction(
    payload: UrlAnalyzeRequest,
    app: FastAPI,
    background_tasks: BackgroundTasks,
    repos: Repositories,
    user_id: str,
):
    post_url = payload.url
    session_id = payload.session_id

    try:
        new_item_id = await repos.saved_posts.create_processing_item(user_id, post_url)
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"임시 데이터 저장 실패: {exc}") from exc

    background_tasks.add_task(
        background_crawl_and_save,
        app,
        new_item_id,
        user_id,
        post_url,
        session_id,
    )

    return {
        "success": True,
        "message": "데이터 추출 및 AI 분석이 시작되었습니다.",
        "item_id": new_item_id,
        "data": [
            {
                "id": new_item_id,
                "url": post_url,
                "category": "PROCESSING",
                "sub_category": "PROCESSING",
                "recommend": "AI가 열심히 바이브를 추출하고 있어요",
                "facts": {"title": "분석 중..."},
                "image_url": "",
            }
        ],
    }


async def background_pse_search(
    app: FastAPI,
    user_id: str,
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
        target_domains = custom_domain_map if custom_domain_map is not None else domain_map

        async with httpx.AsyncClient(timeout=60.0) as client:
            site_tasks = [
                asyncio.create_task(
                    process_site(user_id, manager, model_semaphore, serp_api_key, current_page, query, domain, name, client)
                )
                for domain, name in target_domains.items()
            ]
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


async def save_manual_item_for_user(payload: ManualItemCreate, user_id: str, repos: Repositories):
    try:
        local_image_url, ai_parsed_data = await asyncio.gather(
            _fetch_manual_image(payload),
            _parse_manual_description(payload),
        )
        ai_parsed_data = ai_parsed_data or {}

        facts = payload.facts.copy() if isinstance(payload.facts, dict) else {}
        if ai_parsed_data.get("key_details"):
            facts["key_details"] = ai_parsed_data["key_details"]

        category = payload.category
        sub_category = ai_parsed_data.get("sub_category") or payload.sub_category

        vector_list = await _extract_vector_sync(local_image_url, sub_category or category)
        vector_str = str(vector_list) if vector_list else None

        await repos.saved_posts.create_manual_item(
            user_id=user_id,
            url=payload.url,
            category=category,
            sub_category=sub_category,
            recommend=ai_parsed_data.get("recommend") or payload.recommend,
            facts=facts,
            image_url=local_image_url,
            image_vector=vector_str,
        )
        return {"success": True, "message": "웹 검색 결과가 내 피드로 이동되었습니다."}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"수동 저장 실패: {exc}") from exc


async def _fetch_manual_image(payload: ManualItemCreate) -> str:
    if payload.image_url and payload.image_url.startswith(("http://", "https://")):
        files = await download_images([payload.image_url], str(IMAGE_DIR))
        if files:
            return os.path.basename(files[0])
    return payload.image_url or ""


async def _parse_manual_description(payload: ManualItemCreate) -> dict:
    title = payload.facts.get("title", "") if isinstance(payload.facts, dict) else ""
    if title:
        return await analyze_description_with_gemini(title)
    return {}


async def list_items_for_user(user_id: str, repos: Repositories):
    try:
        items = await repos.saved_posts.list_feed_items(user_id)
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return items
    except Exception as exc:
        print(f"조회 에러: {exc}")
        return []


async def delete_item_for_user(item_id: int, user_id: str, repos: Repositories):
    try:
        await repos.saved_posts.delete_by_id(item_id, user_id)
        await repos.saved_posts.conn.commit()
        return {"success": True}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def resolve_image_path(filename: str) -> Path:
    normal_path = Path(IMAGE_DIR) / filename
    if normal_path.exists() and normal_path.is_file():
        return normal_path

    fail_path = FAIL_IMAGE_DIR / filename
    if fail_path.exists() and fail_path.is_file():
        return fail_path

    raise HTTPException(status_code=404, detail="Image not found")
