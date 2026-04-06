import os
import traceback
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from project.backend.app.core.database import get_repos
from project.backend.app.repositories import Repositories
from project.backend.app.schemas.requests import ManualItemCreate, SearchRequest, UrlAnalyzeRequest
from project.backend.app.services.crawling import DEFAULT_USER_ID, background_crawl_and_save
from project.backend.app.core.settings import load_backend_env
from project.backend.Step3.query_extend_llm import optimize_query_with_llm


load_backend_env()

router = APIRouter()


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
                "vibe_text": "AI가 열심히 바이브를 추출하고 있어요 ",
                "facts": {"title": "분석 중..."},
                "image_url": "",
            }
        ],
    }


@router.post("/pse")
async def run_serpapi_search(payload: SearchRequest):
    serp_api_key = os.environ.get("SERP_API_KEY")
    if not serp_api_key:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")

    url = "https://serpapi.com/search"
    domain_map = {
        "musinsa.com": "무신사",
        "kream.co.kr": "KREAM",
        "fruitsfamily.com": "후루츠패밀리",
        "kasina.co.kr": "카시나",
        "heights-store.com": "하이츠스토어",
        "8division.com": "에잇디비젼",
        "worksout.co.kr": "웍스아웃",
        "iamshop-online.com": "아이엠샵",
        "samplas.co.kr": "샘플라스",
        "etcseoul.com": "etcseoul",
        "zara.com": "자라",
        "fetching.co.kr": "페칭",
        "empty.seoul.kr": "무신사 엠프티"
    }

    extended_query = await optimize_query_with_llm(payload.query)

    site_query = " | ".join([f"site:{domain}" for domain in domain_map])
    product_hierarchy_query = "(> products)"
    exclude_list_pages = "-inurl:search -inurl:category -inurl:tags"
    final_query = f"{extended_query} ({site_query}) {product_hierarchy_query} {exclude_list_pages}"
    print(f"SerpApi로 쏘는 쿼리: {final_query}")

    try:
        current_page = max(1, int(payload.page)) if payload.page is not None else 1
    except ValueError:
        current_page = 1

    params = {
        "engine": "google",
        "q": final_query,
        "api_key": serp_api_key,
        "num": 25,
        "tbm": "isch",
        "start": (current_page - 1) * 25,
        "gl": "kr",
        "hl": "ko",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"SerpApi 에러 내용: {response.text}")
            response.raise_for_status()
            search_data = response.json()

        items = search_data.get("images_results", [])
        print(f"SerpApi가 가져온 전체 원본 데이터 개수: {len(items)}")

        results = []
        for item in items:
            link = item.get("link", "")
            title = item.get("title", "상품명 없음")
            image_url = item.get("original", "") or item.get("thumbnail", "")

            source = item.get("source", "알 수 없는 샵")
            for domain, name in domain_map.items():
                if domain in link:
                    source = name
                    break

            results.append(
                {
                    "id": str(uuid.uuid4()),
                    "category": "PRODUCT",
                    "vibe": f"{source}에서 발견한 힙한 아이템",
                    "image_url": image_url,
                    "url": link,
                    "summary_text": title,
                    "facts": {
                        "title": title,
                        "Price": "가격 미상",
                        "Shop": source,
                    },
                }
            )

        print(f"최종결과 개수: {len(results)}")
        return {"success": True, "results": results}
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"쇼핑 검색 중 오류: {exc}") from exc


@router.post("/items/manual")
async def save_manual_item(
    payload: ManualItemCreate,
    repos: Repositories = Depends(get_repos),
):
    try:
        await repos.saved_posts.create_manual_item(
            user_id=str(payload.user_id),
            url=payload.url,
            category=payload.category,
            vibe=payload.vibe,
            facts=payload.facts,
            image_url=payload.image_url or "",
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
