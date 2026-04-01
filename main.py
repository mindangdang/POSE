import os
import uuid
import html
import asyncio
import httpx
import urllib.parse
from fastapi.responses import Response
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, APIRouter, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from time import time
from psycopg_pool import AsyncConnectionPool
from playwright.async_api import async_playwright
from project.backend.Step1.Rapid_api_crawler import Rapid_crawler
from project.backend.Step1.shopping_crawler import scrape_product_metadata
from project.backend.Step1.instagram_crawler import download_images, crawl_instagram_post
from project.backend.Step2.image_ocr_llm import extract_fact_and_vibe
from project.backend.Step2.insert_DB import insert_items_to_db 
from project.backend.Step2.preferance_llm import analyze_vibe      
from project.backend.Step1.utils import analyze_description_with_gemini
from project.backend.db import (
    create_db_pool,
    create_manual_item,
    create_processing_item,
    delete_saved_post_by_id,
    fetch_items,
    fetch_taste_profile,
    get_db_connection as get_pooled_db_connection,
    get_latest_taste_summary,
    init_db,
    upsert_taste_profile,
    count_saved_posts,
)

load_dotenv()
NEON_DB_URL = os.environ.get("NEON_DB_URL")
SERP_API_KEY = os.environ.get("SERP_API_KEY")

pool: AsyncConnectionPool = None

# FastAPI 라이프사이클
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if not NEON_DB_URL:
        raise RuntimeError("NEON_DB_URL environment variable is not set.")
    
    # 트래픽에 맞춰 최소 5개 ~ 최대 20개의 연결을 유지하는 풀 생성
    pool = create_db_pool(conninfo=NEON_DB_URL, min_size=5, max_size=20)
    print("DB 커넥션 풀 생성 완료")
    
    # 풀이 생성되면 테이블 스키마 확인
    await init_db(pool)
    
    yield  # === 여기서 FastAPI 앱 동작 ===
    
    await pool.close()
    print("DB 커넥션 풀 안전하게 종료됨")

app = FastAPI(lifespan=lifespan)

# ==========================================
# 2. 앱 설정 및 미들웨어
# ==========================================
if not os.path.exists("insta_vibes"):
    os.makedirs("insta_vibes")
app.mount("/api/images", StaticFiles(directory="insta_vibes"), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #  배포 시 실제 도메인으로 변경 필수!
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 의존성(Dependency) 주입 함수
async def get_db_connection():
    async for conn in get_pooled_db_connection(pool):
        yield conn

# ==========================================
# 3. Pydantic Models 
# ==========================================
class UrlAnalyzeRequest(BaseModel):
    url: str
    session_id: Optional[str] = None

class TasteUpdate(BaseModel):
    summary: str

class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = 1

class FeedbackRequest(BaseModel):
    user_id: str | int
    query: str
    result: str
    feedback_type: str  # 'like' or 'dislike'
    reason: Optional[str] = ""

class ManualItemCreate(BaseModel):
    user_id: str | int
    category: str
    vibe: str
    facts: dict
    url: str
    image_url: Optional[str] = ""

# ==========================================
# 4. [백그라운드 워커] 무거운 크롤링 전담  
# ==========================================
async def background_crawl_and_save(item_id: int, user_id: str, post_url: str, session_id: Optional[str], rapid_api_key: Optional[str]):
    print(f"[백그라운드] 작업 시작: {post_url}")
    try:
        crawl_result = None
        is_instagram = "instagram.com" in post_url.lower()
        extracted_items = []
        
        # case1: 인스타 게시물인 경우
        if is_instagram:
            if rapid_api_key:
                crawl_result = await Rapid_crawler(post_url) 
            else:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    context = await browser.new_context(user_agent="Mozilla/5.0...")
                    await context.add_cookies([{"name": "sessionid", "value": session_id, "domain": ".instagram.com", "path": "/", "httpOnly": True, "secure": True}])
                    page = await context.new_page()
                    crawl_result = await crawl_instagram_post(page, post_url) 
                    await browser.close()

            if not crawl_result or crawl_result.get("error"):
                print(f"[백그라운드] 크롤링 실패: {crawl_result.get('error')}")
                return

            raw_downloaded_files = await download_images(crawl_result.get("image_urls", []), "insta_vibes")
            downloaded_files = []
            
            for old_path in raw_downloaded_files:
                if os.path.exists(old_path):
                    ext = os.path.splitext(old_path)[1] or '.jpg'
                    new_filename = f"{uuid.uuid4().hex}{ext}"
                    new_path = os.path.join("insta_vibes", new_filename)
                    os.rename(old_path, new_path)
                    downloaded_files.append(new_path)
                    
            try:
                ai_result = await asyncio.to_thread(
                    extract_fact_and_vibe,
                    downloaded_files, 
                    crawl_result.get("caption", ""),  
                    crawl_result.get("hashtags", []) 
                )
                extracted_items = ai_result.get("extracted_items", [])
                
                for item in extracted_items:
                    image_index = int(item.get("image_index", 0) or 0)
                    image_path = downloaded_files[image_index] if image_index < len(downloaded_files) else None
                    item["image_url"] = os.path.basename(image_path) if image_path else ""
                    
            except Exception as e:
                print(f"[백그라운드] AI 분석 중 에러 발생: {e}")
                return

        # case2: 인스타 게시물이 아닌 경우
        else:
            data = await scrape_product_metadata(post_url) 
            if not data:
                print("[백그라운드] 웹페이지 정보를 가져올 수 없습니다.")
                return
            
            raw_image_url = data.get("image_url", "")
            normalized_image_url = html.unescape(raw_image_url.strip()) if isinstance(raw_image_url, str) else ""
            if normalized_image_url.startswith("//"):
                normalized_image_url = f"https:{normalized_image_url}"

            local_image_url = ""
            if normalized_image_url.startswith("http://") or normalized_image_url.startswith("https://"):
                downloaded_files = await download_images([normalized_image_url], "insta_vibes")
                if downloaded_files:
                    local_image_url = os.path.basename(downloaded_files[0])
                    print(f"[백그라운드] 외부 상품 이미지를 로컬로 저장 완료: {local_image_url}")
                else:
                    print(f"[백그라운드] 외부 상품 이미지 다운로드 실패, 원본 URL 유지: {normalized_image_url[:120]}")
            
            description = data.get("description", "No description available")
            ai_parsed_data = await analyze_description_with_gemini(description)
            brand_info = data.get("brand", "")
            final_key_details = ai_parsed_data.get("key_details", "")
            if brand_info:
                final_key_details = f"[{brand_info}] {final_key_details}".strip()

            extracted_items = [{
                "category": "PRODUCT", 
                "title": data.get("title", "Unknown"),
                "vibe_text": ai_parsed_data.get("vibe_text", "No description available"), 
                "image_url": local_image_url or normalized_image_url, 
                "facts": {
                    "title": data.get("title", ""),
                    "price_info": f"{data.get('price', '')} {data.get('currency', '')}".strip(),
                    "location_text": data.get("source", ""),
                    "key_details": final_key_details
                }
            }]

        if not extracted_items:
            raise Exception("추출된 데이터가 없습니다.")

        try:
            async with pool.connection() as conn:
                await delete_saved_post_by_id(conn, item_id)

                # 빌려온 conn을 그대로 전달하여 내부에서 재사용
                user_id = "1"
                await insert_items_to_db(user_id, post_url, extracted_items, conn=conn)

                # 최종 커밋
                await conn.commit()
                print(f"[백그라운드] 작업 및 DB 저장 완료")

        except Exception as e:
            print(f"[백그라운드] 에러: {str(e)}")

    except Exception as e:
        print(f"[백그라운드] 전체 프로세스 에러: {str(e)}")


# ==========================================
# 5. API 라우터 (Endpoints)
# ==========================================

# [API 1] 크롤링 & 데이터 추출 (즉시 응답)
@app.post("/api/extract-url")
async def extract_and_save_url(request: UrlAnalyzeRequest, background_tasks: BackgroundTasks, conn = Depends(get_db_connection)):
    post_url = request.url
    session_id = request.session_id
    rapid_api_key = os.environ.get("RAPIDAPI_KEY")
    user_id = "1"
    
    if "instagram.com" in post_url.lower() and not rapid_api_key and not session_id:
        raise HTTPException(status_code=400, detail="RapidAPI 키가 없으므로 SESSION_ID가 필요합니다.")

    # 1. DB에 '처리 중(PROCESSING)' 상태의 빈 껍데기 선 저장
    try:
        new_item_id = await create_processing_item(conn, user_id, post_url)
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=f"임시 데이터 저장 실패: {str(e)}")

    # 2. 백그라운드 큐에 할당 
    background_tasks.add_task(background_crawl_and_save, new_item_id, user_id, post_url, session_id, rapid_api_key)
    
    # 3. 즉시 리턴 
    return {
        "success": True, 
        "message": "데이터 추출 및 AI 분석이 시작되었습니다.", 
        "item_id": new_item_id,
        "data": [{
            "id": new_item_id,
            "url": post_url,
            "category": "PROCESSING ",
            "vibe_text": "AI가 열심히 바이브를 추출하고 있어요 ",
            "facts": {"title": "분석 중..."},
            "image_url": "" 
        }]
    }

# [API 2] 취향 프로필 생성
@app.post("/api/generate-taste")
async def generate_taste_profile(conn = Depends(get_db_connection)):
    try:
        # 1. 아이템 존재 여부 체크
        count = await count_saved_posts(conn, "1")
        if count == 0:
            return {"success": False, "message": "피드에 아이템이 없습니다. 먼저 아이템을 추가해 주세요."}

        existing_summary = await get_latest_taste_summary(conn)
        current_profile = {"persona": "정보 없음", "unconscious_taste": "데이터 부족", "recommendation": "데이터 부족"}

        if existing_summary:
            try:
                parts = existing_summary.split("\n\n")
                current_profile["persona"] = parts[0].replace("**페르소나**\n", "")
                current_profile["unconscious_taste"] = parts[1].replace("**나도 몰랐던 나의 취향**\n", "")
                current_profile["recommendation"] = parts[2].replace("**추천**\n", "")
            except Exception:
                pass

        # 분석 실행
        summary_dict = await analyze_vibe(user_id=1, current_profile=current_profile)

        if not summary_dict:
            return {"success": False, "message": "취향 분석에 실패했습니다."}

        final_summary_text = (
            f"**페르소나**\n{summary_dict.get('persona', '분석 불가')}\n\n"
            f"**나도 몰랐던 나의 취향**\n{summary_dict.get('unconscious_taste', '내용 없음')}\n\n"
            f"**추천**\n{summary_dict.get('recommendation', '추천 없음')}"
        )

        try:
            await upsert_taste_profile(conn, final_summary_text)
            print(f"DB 저장 성공: {final_summary_text[:30]}...")
        except Exception as db_e:
            await conn.rollback()
            print(f"DB 실행 중 에러 발생: {db_e}")
            raise db_e

        # 5. 프론트엔드 응답 (조립된 텍스트 전달)
        return {"success": True, "summary": final_summary_text}

    except Exception as e:
        # 에러 로깅 강화
        import traceback
        print(f"generate_taste_profile 최종 에러: {str(e)}")
        print(traceback.format_exc()) # 어디서 .get()이 터졌는지 정확히 알려줌
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# [API 3] pse
@app.post("/api/pse")
async def run_serpapi_search(request: SearchRequest):
    if not SERP_API_KEY:
        raise HTTPException(status_code=500, detail="SerpApi 키가 설정되지 않았습니다.")

    url = "https://serpapi.com/search"

    domain_map = {
        "musinsa.com": "무신사",
        "kream.co.kr": "KREAM",
        "fruitsfamily.com": "후루츠패밀리"
    }
    
    site_query = " | ".join([f"site:{domain}" for domain in domain_map.keys()])
    product_hierarchy_query = "(> products)"
    exclude_list_pages = "-inurl:search -inurl:category -inurl:tags"
    final_query = f"{request.query} ({site_query}) {product_hierarchy_query} {exclude_list_pages}"
    print(f"SerpApi로 쏘는 쿼리: {final_query}")

    try:
        current_page = max(1, int(request.page)) if request.page is not None else 1
    except ValueError:
        current_page = 1
    start_index = (current_page - 1) * 25

    params = {
        "engine": "google",
        "q": final_query,
        "api_key": SERP_API_KEY,
        "num": 25,
        "tbm": "isch",
        "start": start_index, # 페이징 적용
        "gl": "kr",
        "hl": "ko"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"SerpApi 에러 내용: {response.text}")
                
            response.raise_for_status()
            search_data = response.json()

        items = search_data.get("images_results", [])
        results = []
        print(f"SerpApi가 가져온 전체 원본 데이터 개수: {len(items)}")

        for i, item in enumerate(items):
            link = item.get("link", "") # 상품 페이지 링크
            title = item.get("title", "상품명 없음")
            
            # SerpApi 이미지 검색은 'original'(고화질)과 'thumbnail'(저화질) 둘 다 줌
            image_url = item.get("original", "") 
            if not image_url:
                image_url = item.get("thumbnail", "")

            # 출처(Source) 매핑 (기존 로직 동일)
            source = item.get("source", "알 수 없는 샵") # 이미지 검색은 source도 깔끔하게 줌
            for domain, name in domain_map.items():
                if domain in link:
                    source = name
                    break
            
            # 가격 정보: 이미지 검색 API는 가격을 별도로 안 줄 때가 많음
            # 제목(title)에 가격이 섞여 있는 경우가 아니면 일단 '가격 미상'으로 처리
            price = "가격 미상" 

            card_item = {
                "id": str(uuid.uuid4()), 
                "category": "PRODUCT",   
                "vibe": f"{source}에서 발견한 힙한 아이템", 
                "image_url": image_url,
                "url": link,
                "summary_text": title,
                "facts": {
                    "title": title,
                    "Price": price, # 가격이 꼭 필요하다면 별도 크롤링 봇을 태워야 함
                    "Shop": source
                }
            }
            results.append(card_item)
        
        print(f"최종결과 개수: {len(results)}")
        return {"success": True, "results": results}


    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"쇼핑 검색 중 오류: {str(e)}")

# [API 4] pse 검색결과 아이템 피드로 이동
@app.post("/api/items/manual")
async def save_manual_item(request: ManualItemCreate, conn = Depends(get_db_connection)):
    try:
        await create_manual_item(
            conn,
            user_id=str(request.user_id),
            url=request.url,
            category=request.category,
            vibe=request.vibe,
            facts=request.facts,
            image_url=request.image_url or "",
        )
        return {"success": True, "message": "웹 검색 결과가 내 피드로 이동되었습니다."}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=f"수동 저장 실패: {str(e)}")
    
# ==========================================
# 6. 일반 CRUD 및 SPA 서빙 엔드포인트
# ==========================================
@app.get("/api/items")
async def get_items(user_id: str = "1", conn = Depends(get_db_connection)):
    try:
        items = await fetch_items(conn, user_id)
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return items
    except Exception as e:
        print(f"조회 에러: {e}")
        return []

@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int, conn = Depends(get_db_connection)):
    try:
        await delete_saved_post_by_id(conn, item_id)
        await conn.commit()
        return {"success": True}
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/taste")
async def get_taste(conn = Depends(get_db_connection)):
    try:
        return await fetch_taste_profile(conn)
    except Exception as e:
        print(f"취향 프로필 조회 에러: {e}")
        return {"summary": ""}

@app.get("/api/debug/dist")
def debug_dist():
    exists = os.path.exists("dist")
    contents = os.listdir("dist") if exists else []
    return {"exists": exists, "contents": contents, "cwd": os.getcwd()}

if os.path.exists("dist"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API route not found: {full_path}")
    
    if not full_path or full_path == "/":
        if os.path.exists("dist/index.html"):
            return FileResponse("dist/index.html")
    
    file_path = os.path.join("dist", full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html")
    
    return {"error": "Frontend not built or route not found"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
