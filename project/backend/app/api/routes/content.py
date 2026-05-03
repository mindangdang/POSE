import os
import uuid
import asyncio
import io
import traceback
import json
from PIL import Image
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
from project.backend.Step3.embedding_reranking import FashionSiglipReRankingPipeline
from project.backend.Step2.insert_DB import _extract_vector_sync
from project.backend.Step2.preferance_llm import fetch_user_data_from_neon
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
    user_id = current_user.get("sub")

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
                "category": "PROCESSING ",
                "sub_category": "PROCESSING ",
                "recommend": "AI가 열심히 바이브를 추출하고 있어요 ",
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
        pipeline = FashionSiglipReRankingPipeline(lambda_weight=0.6)

        # 1 & 2. 유저 취향 벡터 합성과 LLM 쿼리 확장을 비동기 병렬 처리
        async def build_taste_vector():
            # Google ID(sub)는 21자리의 문자열이므로 int 대신 str로 안전하게 넘깁니다.
            wishlist_db_items = await fetch_user_data_from_neon(str(user_id))
            if not wishlist_db_items:
                return None
            print(f"[User {user_id}] 위시리스트 {len(wishlist_db_items)}개 벡터 DB 로딩 및 합성 시작...")
            
            def _parse_vectors_batch(items):
                vectors = []
                for item in items:
                    v_str = item.get("image_vector")
                    if v_str:
                        try:
                            vec = json.loads(v_str)
                            if isinstance(vec, list) and len(vec) == 768:
                                vectors.append(vec)
                        except Exception as e:
                            print(f"벡터 파싱 에러: {e}")
                return vectors

            image_vectors = await asyncio.to_thread(_parse_vectors_batch, wishlist_db_items)
            
            if image_vectors:
                return pipeline.build_user_taste_vector(image_vectors)
            return None

        user_taste_vector, extended_query_result = await asyncio.gather(
            build_taste_vector(),
            optimize_query_with_llm(query)
        )

        extended_query = extended_query_result.get('final_query', query)
        print(f"SerpApi로 쏘는 쿼리: {extended_query}")

        # 3. SerpApi로 여러 쇼핑몰에서 검색 (병렬)
        try:
            current_page = max(1, int(page)) if page is not None else 1
        except ValueError:
            current_page = 1

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
        }

        query_vector = pipeline.encode_text(query)
        dl_semaphore = asyncio.Semaphore(20)
        model_semaphore = asyncio.Semaphore(4)
        
        async def process_single_item(item: dict, dl_client: httpx.AsyncClient):
            target_url = item.get("image_url")
            if not target_url:
                return
                
            async with dl_semaphore:
                image_obj = None
                for attempt in range(3):
                    try:
                        resp = await dl_client.get(target_url, headers=headers, timeout=12.0, follow_redirects=True)
                        resp.raise_for_status()
                        
                        # 이미지 디코딩/변환(CPU 바운드 작업)을 스레드로 넘겨 이벤트 루프 블로킹 방지
                        def _load_image():
                            return Image.open(io.BytesIO(resp.content)).convert("RGB")
                        image_obj = await asyncio.to_thread(_load_image)
                        break
                    except Exception as e:
                        if attempt == 2:
                            print(f"이미지 다운로드 실패 ({target_url[:50]}...): {e}")
                        else:
                            await asyncio.sleep(0.5)
                
                if image_obj is None:
                    return
                item["image_obj"] = image_obj

            async with model_semaphore:
                await asyncio.sleep(0.01)
                evaluated_item = await asyncio.to_thread(
                    pipeline.evaluate_single_item,
                    item,
                    user_taste_vector,
                    query_vector,
                    0.10,
                    0.0
                )

            if evaluated_item:
                print("아이템이 임계값 통과, 프론트로 전송 준비 완료.")
                evaluated_item.pop("image_obj", None)
                evaluated_item.pop("original_url", None)
                evaluated_item.pop("thumbnail_url", None)
                
                if manager:
                    payload = {
                        "type": "SEARCH_SUCCESS",
                        "results": [evaluated_item],
                        "is_append": True
                    }
                    await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
                    # Uvicorn의 전송 큐가 처리될 수 있도록 루프 권한 양보
                    await asyncio.sleep(0.01)
                    print("아이템이 프론트로 전송되었습니다.")

        async def process_site(domain: str, name: str, client: httpx.AsyncClient, dl_client: httpx.AsyncClient):
            try:
                site_items = await fetch_from_single_site(client, extended_query, domain, name, current_page, serp_api_key)
                if isinstance(site_items, list) and site_items:
                    if user_taste_vector is not None:
                        eval_tasks = [asyncio.create_task(process_single_item(item, dl_client)) for item in site_items]
                        await asyncio.gather(*eval_tasks, return_exceptions=True)
                    else:
                        if manager:
                            payload = {"type": "SEARCH_SUCCESS", "results": site_items, "is_append": True}
                            await manager.broadcast_to_user(user_id, json.dumps(payload, default=str))
                            await asyncio.sleep(0.01)
            except Exception as e:
                print(f"쇼핑몰 검색 스트리밍 처리 에러: {e}")

        print("여러 쇼핑몰 병렬 검색 및 실시간 평가 시작...")
        # 모든 이미지 다운로드를 위한 단일 HTTP/2 클라이언트를 공유하여 속도 개선
        async with httpx.AsyncClient(timeout=None) as client, httpx.AsyncClient(timeout=None, http2=True) as dl_client:
            site_tasks = [asyncio.create_task(process_site(domain, name, client, dl_client)) for domain, name in domain_map.items()]
            await asyncio.gather(*site_tasks)
            
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

    user_id = current_user.get("sub")
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
        # timeout=None으로 구글 렌즈 검색이 끝날 때까지 무조건 대기
        async with httpx.AsyncClient(timeout=None) as client:
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
async def fetch_lens_multisearch_with_file(image: UploadFile, user_text: str = Form(...)):  

    serp_api_key = os.environ.get("SERP_API_KEY")
    if not serp_api_key:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")
    
    url = "https://serpapi.com/search"
    print(f"[Multisearch] 파일 업로드 방식 검색 시작...")
    
    image_bytes = await image.read()
    search_image_url = await upload_generated_image(image_bytes)

    params = {
        "engine": "google_lens",
        "q": user_text,
        "url": search_image_url,
        "tbm": "isch", 
        "type": "visual_matches",
        "api_key": serp_api_key,
        "hl": "ko", "gl": "kr"
    }

    try:
        # timeout=None으로 구글 렌즈 멀티모달 검색이 끝날 때까지 무조건 대기
        async with httpx.AsyncClient(timeout=None) as client:
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

        # 4. 임베딩 벡터 추출 (비동기 스레드 실행)
        vector_list = await asyncio.to_thread(_extract_vector_sync, local_image_url, sub_category or category)
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
        await repos.saved_posts.delete_by_id(item_id)
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
