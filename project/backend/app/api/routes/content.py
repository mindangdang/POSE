import os
import uuid
import asyncio
import traceback
import json
from typing import Optional
import httpx
from pathlib import Path

from fastapi import (
    FastAPI,
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    Form,
    File,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from project.backend.app.core.database import get_repos
from project.backend.app.repositories import Repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.services.crawling import background_crawl_and_save
from project.backend.app.core.settings import load_backend_env
from project.backend.Step3.query_extend_llm import optimize_query_with_llm
from project.backend.Step3.image_search import generate_image_from_query,upload_generated_image
from project.backend.Step1.utils import *
from project.backend.Step1.instagram_crawler import download_images
from project.backend.app.core.settings import IMAGE_DIR
from project.backend.Step2.insert_DB import _extract_vector_sync
from project.backend.app.api.routes.auth import get_current_user

load_backend_env()
LOCAL_IMAGE_DIR = Path(IMAGE_DIR)

router = APIRouter()

# 메모리 주소가 보장된 단일 매니저 전역 객체 생성
websocket_manager_instance = ConnectionManager()

@router.post("/extract-url")
async def extract_and_save_url(
    payload: UrlAnalyzeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    repos: Repositories = Depends(get_repos),
    current_user: dict = Depends(get_current_user)
):
    post_url = payload.url
    session_id = payload.session_id
    rapid_api_key = os.environ.get("RAPIDAPI_KEY")
    user_id = str(current_user.get("sub"))

    if "instagram.com" in post_url.lower() and not rapid_api_key and not session_id:
        raise HTTPException(status_code=400, detail="RapidAPI 키가 없으므로 SESSION_ID가 필요합니다.")

    request.app.state.websocket_manager = websocket_manager_instance

    try:
        new_item_id = await repos.saved_posts.create_processing_item(user_id, post_url)
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=f"임시 데이터 저장 실패: {exc}") from exc

    background_tasks.add_task(
        background_crawl_and_save,
        request.app,
        new_item_id,
        user_id,
        post_url,
        session_id,
        rapid_api_key,
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

######################################################################################

async def background_pse_search(app: FastAPI, user_id: str, query: str, page: int):
    manager = getattr(app.state, "websocket_manager", None)
    serp_api_key = os.environ.get("SERP_API_KEY")
    
    if not serp_api_key:
        if manager:
            payload = {"type": "SEARCH_ERROR", "message": "SerpApi 키가 설정되지 않았습니다."}
            await manager.broadcast_to_user(user_id, json.dumps(payload))
        return

    try:
        # 1. 유저 취향 프로필(Consensus + Memory) 합성과 LLM 쿼리 확장, 쿼리 임베딩을 비동기 병렬 처리
        user_taste_profile, extended_query_result, query_vector = await asyncio.gather(
            build_taste_profile(user_id),
            optimize_query_with_llm(query),
            encode_text(query)
        )

        extended_query = extended_query_result.get('final_query', query)
        print(f"SerpApi로 쏘는 쿼리: {extended_query}")

        if query_vector is None:
            print("쿼리 벡터 추출 실패. 검색을 중단합니다.")
            if manager:
                await manager.broadcast_to_user(user_id, json.dumps({"type": "SEARCH_ERROR", "message": "쿼리 벡터 추출 실패"}))
            return

        # 3. SerpApi로 여러 쇼핑몰에서 검색 (병렬)
        try:
            current_page = max(1, int(page)) if page is not None else 1
        except ValueError:
            current_page = 1

        model_semaphore = asyncio.Semaphore(4)
        
        async def process_single_item(item: dict):
            try:
                target_url = item.get("image_url")
                if not target_url:
                    return
                    
                async with model_semaphore:
                    await asyncio.sleep(0.01)
                    evaluated_item = await evaluate_single_item(
                        item,
                        user_taste_profile,
                        query_vector,
                        0.05,  # 모델에게 너무 엄격한 기준일 수 있어 0.05로 하향 조정
                        0.0
                    )

                if evaluated_item:
                    if manager:
                        payload = {
                            "type": "SEARCH_SUCCESS",
                            "results": [evaluated_item],
                            "is_append": True
                        }
                        await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
                        # Uvicorn의 전송 큐가 처리될 수 있도록 루프 권한 양보
                        await asyncio.sleep(0.01)
                        print(f"[{item.get('summary_text', 'Unknown')}] 임계값 통과! 프론트로 전송 완료.")
                else:
                    print(f"[{item.get('summary_text', 'Unknown')}] GPU 서버 평가 탈락 (임계값 미달 또는 오류)")
            except Exception as e:
                print(f"개별 아이템 평가 에러: {e}")

        async def process_site(domain: str, name: str, client: httpx.AsyncClient):
            try:
                site_items = await fetch_from_single_site(client, extended_query, query, domain, name, current_page, serp_api_key)
                if user_taste_profile is not None:
                    eval_tasks = [asyncio.create_task(process_single_item(item)) for item in site_items]
                    await asyncio.gather(*eval_tasks, return_exceptions=True)
                else:
                    print(f"[{name}] 취향 벡터가 없어 평가 없이 즉시 프론트로 전송: {len(site_items)}개")
                    if manager:
                        payload = {"type": "SEARCH_SUCCESS", "results": site_items, "is_append": True}
                        await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
                        await asyncio.sleep(0.01)
            except Exception as e:
                print(f"쇼핑몰 검색 스트리밍 처리 에러: {e}")

        print("여러 쇼핑몰 병렬 검색 및 실시간 평가 시작...")
        # 모든 이미지 다운로드를 위한 단일 HTTP/2 클라이언트를 공유하여 속도 개선
        async with httpx.AsyncClient(timeout=60.0) as client:
            site_tasks = [asyncio.create_task(process_site(domain, name, client)) for domain, name in domain_map.items()]
            await asyncio.gather(*site_tasks, return_exceptions=True)
            
        print("모든 쇼핑몰 검색 및 스트리밍 완료.")
        
        if manager:
            await manager.broadcast_to_user(user_id, json.dumps({"type": "SEARCH_FINISHED"}))
    
    except Exception as exc:
        traceback.print_exc()
        if manager:
            payload = {"type": "SEARCH_ERROR", "message": f"쇼핑 검색 중 오류: {exc}"}
            await manager.broadcast_to_user(user_id, json.dumps(payload))

@router.post("/pse")
async def run_serpapi_search(
    payload: SearchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    request.app.state.websocket_manager = websocket_manager_instance

    user_id = str(current_user.get("sub"))
    background_tasks.add_task(background_pse_search, request.app, user_id, payload.query, payload.page)

    return {"success": True, "message": "웹 검색 및 AI 분석이 백그라운드에서 시작되었습니다."}

######################################################################################

@router.post("/lens")
async def run_serpapi_lens_search(payload: SearchRequest):
    serp_api_key = os.environ.get("SERP_API_KEY")
    if not serp_api_key:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")

    url = "https://serpapi.com/search"
    image = await generate_image_from_query(payload.query)
    search_image_url = await upload_generated_image(image)

    params = {
        "engine": "google_lens",  
        "url": search_image_url, 
        "api_key": serp_api_key,
        "hl": "ko",
        "gl": "kr"
    }

    print(f"SerpApi(Google Lens)로 디깅 시작: {search_image_url}")

    try:
        # 무한 대기 방지를 위한 안전한 타임아웃 설정
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"SerpApi 에러 내용: {response.text}")
            response.raise_for_status()
            search_data = response.json()

        items = search_data.get("visual_matches", [])
        print(f"구글 렌즈가 가져온 전체 원본 데이터 개수: {len(items)}")

        results = []
        for item in items:
            link = item.get("link", "")
            title = item.get("title", "상품명 없음")
            image_url = item.get("thumbnail", "")
            extracted_price = item.get("price", "가격 미상")
            if isinstance(extracted_price, dict):
                extracted_price = extracted_price.get("value", "")
            source = item.get("source", "알 수 없는 샵")

            results.append(
                {
                    "id": str(uuid.uuid4()),
                    "category": "PRODUCT",
                    "sub_category": "PRODUCT",
                    "recommend": f"{source}에서 발견한 힙한 아이템",
                    "image_url": image_url,
                    "url": link,
                    "summary_text": title,
                    "facts": {
                        "title": title,
                        "Price": extracted_price,
                        "Shop": source,
                    },
                }
            )

        print(f" 통과한 최종결과 개수: {len(results)}")
        return {"success": True, "results": results}
        
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"구글 렌즈 검색 중 오류: {exc}") from exc

######################################################################################

@router.post("/multimodal")
async def fetch_lens_multisearch_with_file(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    user_text: Optional[str] = Form(None)
):  

    serp_api_key = os.environ.get("SERP_API_KEY")
    if not serp_api_key:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")
    
    url = "https://serpapi.com/search"
    print(f"[Multisearch] 멀티모달 검색 시작...")
    
    if image and image.filename:
        image_bytes = await image.read()
        search_image_url = await upload_generated_image(image_bytes)
    elif image_url:
        search_image_url = image_url
    else:
        raise HTTPException(status_code=400, detail="이미지 파일 또는 URL이 필요합니다.")

    params = {
        "engine": "google_lens",
        "url": search_image_url,
        "type": "visual_matches",
        "api_key": serp_api_key,
        "hl": "ko", "gl": "kr"
    }

    if user_text:
        params["q"] = user_text

    try:
        # 무한 대기 방지를 위한 안전한 타임아웃 설정
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"SerpApi 에러 내용: {response.text}")
            response.raise_for_status()
            search_data = response.json()

        items = search_data.get("visual_matches", [])
        print(f"구글 렌즈가 가져온 전체 원본 데이터 개수: {len(items)}")

        results = []
        for item in items:
            link = item.get("link", "")
            title = item.get("title", "상품명 없음")
            image_url = item.get("thumbnail", "")
            extracted_price = item.get("price", "가격 미상")
            if isinstance(extracted_price, dict):
                extracted_price = extracted_price.get("value", "")
            source = item.get("source", "알 수 없는 샵")

            results.append(
                {
                    "id": str(uuid.uuid4()),
                    "category": "PRODUCT",
                    "sub_category": "PRODUCT",
                    "recommend": f"{source}에서 발견한 아이템",
                    "image_url": image_url,
                    "url": link,
                    "summary_text": title,
                    "facts": {
                        "title": title,
                        "Price": extracted_price,
                        "Shop": source,
                    },
                }
            )

        print(f" 통과한 최종결과 개수: {len(results)}")
        return {"success": True, "results": results}
        
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"구글 렌즈 검색 중 오류: {exc}") from exc

######################################################################################

@router.post("/items/manual")
async def save_manual_item(
    payload: ManualItemCreate,
    repos: Repositories = Depends(get_repos),
    current_user: dict = Depends(get_current_user)
):
    try:
        async def fetch_image_task() -> str:
            if payload.image_url and payload.image_url.startswith(("http://", "https://")):
                files = await download_images([payload.image_url], str(IMAGE_DIR))
                if files:
                    return os.path.basename(files[0])
            return payload.image_url or ""

        async def parse_description_task() -> dict:
            title = payload.facts.get("title", "") if isinstance(payload.facts, dict) else ""
            if title:
                return await analyze_description_with_gemini(title)
            return {}

        # 1 & 2. 이미지 다운로드와 Gemini 분석을 비동기로 동시 실행하여 속도 최적화
        local_image_url, ai_parsed_data = await asyncio.gather(
            fetch_image_task(),
            parse_description_task()
        )
        ai_parsed_data = ai_parsed_data or {}

        # 3. 분석된 데이터를 기반으로 facts 키 표준화 및 업데이트
        facts = payload.facts.copy() if isinstance(payload.facts, dict) else {}
        if ai_parsed_data.get("key_details"):
            facts["key_details"] = ai_parsed_data["key_details"]

        category = payload.category
        sub_category = ai_parsed_data.get("sub_category") or payload.sub_category

        # 4. 임베딩 벡터 추출
        vector_list = await _extract_vector_sync(local_image_url, sub_category or category)
        vector_str = str(vector_list) if vector_list else None

        user_id = current_user.get("sub")

        await repos.saved_posts.create_manual_item(
            user_id=str(user_id),
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
    
######################################################################################

@router.get("/items")
async def get_items(
    current_user: dict = Depends(get_current_user), 
    repos: Repositories = Depends(get_repos)
):
    try:
        user_id = current_user.get("sub")
        items = await repos.saved_posts.list_feed_items(str(user_id))
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return items
    except Exception as exc:
        print(f"조회 에러: {exc}")
        return []


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int, 
    current_user: dict = Depends(get_current_user), 
    repos: Repositories = Depends(get_repos)
):
    try:
        await repos.saved_posts.delete_by_id(item_id, str(current_user.get("sub")))
        await repos.saved_posts.conn.commit()
        return {"success": True}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/images/{filename}")
async def serve_image(filename: str):
    image_path = LOCAL_IMAGE_DIR / filename
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path=image_path)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # 동일한 전역 매니저 객체 주소를 앱 상태에 강제 할당
    websocket.app.state.websocket_manager = websocket_manager_instance

    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
