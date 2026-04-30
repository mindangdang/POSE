import os
import traceback
import uuid
import asyncio
import io
import traceback
import json
import torch
from PIL import Image
import httpx
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, Form
from project.backend.app.core.database import get_repos
from project.backend.app.repositories import Repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.services.crawling import DEFAULT_USER_ID, background_crawl_and_save
from project.backend.app.core.settings import load_backend_env
from project.backend.Step3.query_extend_llm import optimize_query_with_llm
from project.backend.Step3.image_search import generate_image_from_query,upload_generated_image
from project.backend.Step1.utils import analyze_description_with_gemini
from project.backend.Step1.instagram_crawler import download_images
from project.backend.app.core.settings import IMAGE_DIR
from project.backend.Step3.embedding_reranking import FashionSiglipReRankingPipeline
from project.backend.Step2.insert_DB import _extract_vector_sync
from project.backend.Step2.preferance_llm import fetch_user_data_from_neon


load_backend_env()
LOCAL_IMAGE_DIR = Path(IMAGE_DIR)

router = APIRouter()

search_tasks: dict = {}

@router.post("/extract-url")
async def extract_and_save_url(
    payload: UrlAnalyzeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    repos: Repositories = Depends(get_repos),
):
    post_url = payload.url
    session_id = payload.session_id
    rapid_api_key = os.environ.get("RAPIDAPI_KEY")
    user_id = DEFAULT_USER_ID

    if "instagram.com" in post_url.lower() and not rapid_api_key and not session_id:
        raise HTTPException(status_code=400, detail="RapidAPI 키가 없으므로 SESSION_ID가 필요합니다.")

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


async def background_serpapi_search(task_id: str, payload: SearchRequest):
    try:
        #1.serpapi 검색
        serp_api_key = os.environ.get("SERP_API_KEY")
        if not serp_api_key:
            raise ValueError("SerpApi 키가 설정되지 않았습니다.")

        domain_map = {
            "musinsa.com": "무신사",
            #"kream.co.kr": "KREAM",
            "m.bunjang.co.kr" : "번개장터",
            "fruitsfamily.com": "후루츠패밀리",
            "zara.com": "자라",
            "instagram.com": "인스타그램"
        }

        extended_query = await optimize_query_with_llm(payload.query)
        extended_query = extended_query.get('final_query', payload.query)
        print(f"SerpApi로 쏘는 쿼리: {extended_query}")

        async def fetch_from_single_site(client: httpx.AsyncClient, base_query: str, domain: str, site_name: str, current_page: int, serp_api_key: str) -> list[dict]:
            product_hierarchy_query = "(> products)"
            exclude_list_pages = "-inurl:search -inurl:category -inurl:snap"
            final_query = f"{base_query} site:{domain} {product_hierarchy_query} {exclude_list_pages}"
            
            params = {
                "engine": "google",
                "q": final_query,
                "api_key": serp_api_key,
                "num": 5, 
                "tbm": "isch",
                "start": (current_page - 1) * 5,
                "gl": "kr",
                "hl": "ko"
            }
            
            try:
                response = await client.get("https://serpapi.com/search", params=params)
                response.raise_for_status()
                items = response.json().get("images_results", [])
                print(f"[{site_name}] 검색 성공")
                
                return [{
                    "id": str(uuid.uuid4()),
                    "category": "PRODUCT",
                    "sub_category": "PRODUCT",
                    "recommend": f"{site_name}에서 발견한 아이템",
                    "image_url": item.get("thumbnail", "") if "instagram" in domain else (item.get("original", "") or item.get("thumbnail", "")),
                    "url": item.get("link", ""),
                    "summary_text": item.get("title", "상품명 없음"),
                    "facts": {
                        "title": item.get("title", "상품명 없음"),
                        "Price": item.get("price") or item.get("snippet") or "가격 미상",
                        "Shop": site_name,
                    },
                } for item in items]

            except Exception as e:
                print(f"[{domain}] 검색 실패: {e}")
                return []

        try:
            current_page = max(1, int(payload.page)) if payload.page is not None else 1
        except ValueError:
            current_page = 1

        #2. 리랭킹 파이프라인
        user_id=1
        pipeline = FashionSiglipReRankingPipeline(lambda_weight=0.6)
        wishlist_db_items = await fetch_user_data_from_neon(user_id)
        
        user_taste_vector = None
        if wishlist_db_items:
            print(f"[User {user_id}] 위시리스트 {len(wishlist_db_items)}개 벡터 DB 로딩 및 합성 시작...")
            
            def _parse_vector_sync(v_str: str):
                try:
                    vec = json.loads(v_str)
                    if isinstance(vec, list) and len(vec) == 768:
                        return vec
                except Exception as e:
                    print(f"벡터 파싱 에러: {e}")
                return None

            parse_tasks = [
                asyncio.to_thread(_parse_vector_sync, item.get("image_vector"))
                for item in wishlist_db_items if item.get("image_vector")
            ]
            parsed_results = await asyncio.gather(*parse_tasks)
            image_vectors = [vec for vec in parsed_results if vec is not None]
            
            if image_vectors:
                user_taste_vector = pipeline.build_user_taste_vector(image_vectors)

        # 예외 처리 (위시리스트가 없거나 경로 에러로 다 날아간 경우 Cold Start 대비)
        if user_taste_vector is None:
            print("유저 취향 데이터가 부족하여 더미(Neutral) 벡터로 대체합니다.")
            dummy = torch.zeros(1, 768).to(pipeline.device) # SigLIP 768차원 기준
            user_taste_vector = torch.nn.functional.normalize(dummy, p=2, dim=1)
            if pipeline.device == "cuda":
                user_taste_vector = user_taste_vector.to(torch.bfloat16)

        # 2. Scatter: 타겟 사이트 병렬 검색
        # timeout=None으로 설정하여 SerpApi 응답이 아무리 느려도 끝까지 대기
        async with httpx.AsyncClient(timeout=None) as client:
            tasks = [
                fetch_from_single_site(client, extended_query, domain, name, current_page, serp_api_key)
                for domain, name in domain_map.items()
            ]
            results_per_site = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. 데이터 평탄화 
        raw_items = [item for sublist in results_per_site if isinstance(sublist, list) for item in sublist]
        
        if not raw_items:
            search_tasks[task_id]["status"] = "completed"
            search_tasks[task_id]["results"] = []
            return

        # 4. In-Memory 스트리밍 다운로드 파이프라인
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
        }
        
        async def download_image_to_memory(dl_client: httpx.AsyncClient, item: dict, semaphore: asyncio.Semaphore):
            target_url = item.get("image_url")
            if not target_url:
                return None
                
            async with semaphore:
                for attempt in range(3):  # 최대 3회 재시도
                    try:
                        resp = await dl_client.get(target_url, headers=headers, timeout=12.0, follow_redirects=True)
                        resp.raise_for_status()
                        
                        # 디스크 I/O 없이 바이트 스트림을 즉시 PIL 객체로 변환
                        item["image_obj"] = Image.open(io.BytesIO(resp.content)).convert("RGB")
                        return item
                    except Exception as e:
                        if attempt == 2:
                            print(f"이미지 스트리밍 다운로드 3회 실패 ({target_url[:50]}...): {e}")
                        else:
                            await asyncio.sleep(0.5)  # 재시도 전 대기
            return None

        print(f"{len(raw_items)}개 이미지 In-Memory 다운로드 시작...")
        # 전체 타임아웃 해제, http2 활성화 및 동시성 50개 제한 세마포어 적용
        semaphore = asyncio.Semaphore(50)
        async with httpx.AsyncClient(timeout=None, http2=True) as dl_client:
            download_tasks = [download_image_to_memory(dl_client, item, semaphore) for item in raw_items]
            downloaded_items = await asyncio.gather(*download_tasks)
            
        valid_items = [item for item in downloaded_items if item is not None]
        print(f"{len(valid_items)}개 이미지 다운로드 성공, 리랭킹 준비 완료.")

        # 6. 머신러닝 리랭킹 (워커 스레드 위임)
        if valid_items:
            ranked_results = await asyncio.to_thread(
                pipeline.rerank_search_results,
                search_results=valid_items,
                user_taste_vector=user_taste_vector,
                query_text=payload.query,
                semantic_thresh=0.10,
                aesthetic_thresh=0.0
            )
        else:
            ranked_results = []

        # 7. 클라이언트 응답용 데이터 정제 (JSON 직렬화 에러 방지)
        for item in ranked_results:
            item.pop("image_obj", None)
            item.pop("original_url", None)
            item.pop("thumbnail_url", None)

        print(f"최종결과 개수: {len(ranked_results)}")
        search_tasks[task_id]["status"] = "completed"
        search_tasks[task_id]["results"] = ranked_results
    
    except Exception as exc:
        traceback.print_exc()
        search_tasks[task_id]["status"] = "failed"
        search_tasks[task_id]["error"] = f"쇼핑 검색 중 오류: {exc}"

@router.post("/pse")
async def start_serpapi_search(payload: SearchRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    search_tasks[task_id] = {"status": "processing", "results": [], "error": None}
    background_tasks.add_task(background_serpapi_search, task_id, payload)
    return {"success": True, "task_id": task_id, "message": "Search task started."}

@router.get("/pse/status/{task_id}")
async def get_search_status(task_id: str):
    task = search_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task_id": task_id, "status": task["status"], "results": task.get("results", []), "error": task.get("error")}


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

@router.post("/items/manual")
async def save_manual_item(
    payload: ManualItemCreate,
    repos: Repositories = Depends(get_repos),
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

        await repos.saved_posts.create_manual_item(
            user_id=str(payload.user_id),
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


@router.get("/items")
async def get_items(user_id: str = "1", repos: Repositories = Depends(get_repos)):
    try:
        items = await repos.saved_posts.list_feed_items(user_id)
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return items
    except Exception as exc:
        print(f"조회 에러: {exc}")
        return []


@router.delete("/items/{item_id}")
async def delete_item(item_id: int, repos: Repositories = Depends(get_repos)):
    try:
        await repos.saved_posts.delete_by_id(item_id)
        await repos.saved_posts.conn.commit()
        return {"success": True}
    except Exception as exc:
        await repos.saved_posts.conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
