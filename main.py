from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from playwright.sync_api import sync_playwright
from project.backend.Step1.Rapid_api_crawler import Rapid_crawler
from project.backend.Step1.shopping_crawler import scrape_product_metadata
from project.backend.Step1.instagram_crawler import download_images, crawl_instagram_post
from project.backend.Step2.image_ocr_llm import extract_fact_and_vibe
from project.backend.Step2.insert_DB import insert_items_to_db 
from project.backend.Step2.preferance_llm import analyze_vibe
from project.backend.Step3.main_agent import VibeSearchAgent          

app = FastAPI()
load_dotenv()

# insta_vibes 폴더를 생성하고 정적 파일을 /api/images/...로 서빙합니다.
if not os.path.exists("insta_vibes"):
    os.makedirs("insta_vibes")
app.mount("/api/images", StaticFiles(directory="insta_vibes"), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

NEON_DB_URL = os.environ.get("NEON_DB_URL")

def get_db():
    if not NEON_DB_URL:
        raise HTTPException(status_code=500, detail="NEON_DB_URL environment variable is not set.")
    conn = psycopg2.connect(NEON_DB_URL)
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
      CREATE TABLE IF NOT EXISTS saved_posts (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        source_url TEXT,
        title TEXT,
        category TEXT,
        summary_text TEXT,
        image_url TEXT,
        vibe_text TEXT,
        vibe_vector vector(768),
        facts JSONB,
        reviews JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_url, title)
      );
    """)

    # 기존 테이블에 image_url 컬럼이 없을 경우 추가
    cursor.execute("""
      ALTER TABLE saved_posts
      ADD COLUMN IF NOT EXISTS image_url TEXT;
    """)

    # 기존 테이블에 reviews 컬럼이 없을 경우 추가
    cursor.execute("""
      ALTER TABLE saved_posts
      ADD COLUMN IF NOT EXISTS reviews JSONB;
    """)
    
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS taste_profile (
        id INTEGER PRIMARY KEY DEFAULT 1,
        summary TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT one_row CHECK (id = 1)
      );
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    print(f"DB 초기화 중 경고: {e}")

class UrlAnalyzeRequest(BaseModel):
    url: str
    session_id: Optional[str] = None

class TasteUpdate(BaseModel):
    summary: str

class SearchRequest(BaseModel):
    query: str

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


# [API 1] 크롤링 & 데이터 추출
@app.post("/api/extract-url")
def extract_and_save_url(request: UrlAnalyzeRequest):
    post_url = request.url
    session_id = request.session_id
    rapid_api_key = os.environ.get("RAPIDAPI_KEY")
    
    crawl_result = None
    is_instagram = "instagram.com" in post_url.lower()
    # case1:인스타 게시물인 경우
    if is_instagram:
        if rapid_api_key:
            crawl_result = Rapid_crawler(post_url)
        else:
            if not session_id:
                raise HTTPException(status_code=400, detail="RapidAPI 키가 없으므로 SESSION_ID가 필요합니다.")
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    context = browser.new_context(user_agent="Mozilla/5.0...")
                    context.add_cookies([{"name": "sessionid", "value": session_id, "domain": ".instagram.com", "path": "/", "httpOnly": True, "secure": True}])
                    page = context.new_page()
                    crawl_result = crawl_instagram_post(page, post_url)
                    browser.close()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Playwright 에러: {str(e)}")

        if not crawl_result or crawl_result.get("error"):
            raise HTTPException(status_code=400, detail=f"크롤링 실패: {crawl_result.get('error')}")

        raw_downloaded_files = download_images(crawl_result.get("image_urls", []), save_dir="insta_vibes")
        downloaded_files = []
        
        # 다운로드된 파일들에 절대 겹치지 않는 랜덤 이름(UUID) 부여
        for old_path in raw_downloaded_files:
            if os.path.exists(old_path):
                ext = os.path.splitext(old_path)[1] or '.jpg'
                new_filename = f"{uuid.uuid4().hex}{ext}"
                new_path = os.path.join("insta_vibes", new_filename)
                os.rename(old_path, new_path)
                downloaded_files.append(new_path)
        try:
            ai_result = extract_fact_and_vibe(
                image_paths=downloaded_files, 
                caption=crawl_result.get("caption", ""),  
                hashtags=crawl_result.get("hashtags", []) 
            )
        except Exception as e:
            print(f"AI 분석 중 에러 발생: {e}")
            return {"success": False, "message": "일부 아이템 분석 실패", "data": []}

        extracted_items = ai_result.get("extracted_items", [])

        # 이미지 파일명(또는 경로)을 각 추출 항목에 주입하여 프론트에서 /api/images/ 경로로 접근할 수 있도록 합니다.
        for item in extracted_items:
            try:
                image_index = int(item.get("image_index", 0) or 0)
                image_path = downloaded_files[image_index] if image_index < len(downloaded_files) else None
                item["image_url"] = os.path.basename(image_path) if image_path else ""
            except Exception:
                item["image_url"] = ""
    
    # case2:인스타 게시물이 아닌 경우
    else:
        data = scrape_product_metadata(request.url)
        if not data:
            raise HTTPException(status_code=400, detail="웹페이지 정보를 가져올 수 없습니다.")
        
        extracted_items = [{
            "category": "PRODUCT", 
            "title": data.get("title", "Unknown"),
            "vibe_text": data.get("description", "No description available"), # 묘사 텍스트
            "image_url": data.get("image_url", ""), # BeautifulSoup으로 뜯어온 진짜 주소
            "facts": {
                "title": data.get("title", ""),
                "price_info": f"{data.get('price', '')} {data.get('currency', '')}".strip(),
                "location_text": data.get("source", ""),
                "key_details": data.get("brand", "")
            }
        }]
    
    # DB 저장 (각 아이템에 user_id를 "1"로 주입하여 저장)
    try:
        user_id = "1" 
        insert_items_to_db(user_id, post_url, extracted_items)
    except Exception as e:
        print(f"DB 저장 중 에러 발생: {e}")
        return {"success": True, "message": "DB 저장 중 오류가 있었으나 데이터는 추출됨", "data": extracted_items}

    # 취향 프로필 업데이트 (아이템 추가 시)
    try:
        summary = analyze_vibe(user_id=1)  
        if summary:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO taste_profile (id, summary, updated_at) VALUES (1, %s, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP",
                (summary,)
            )
            conn.commit()
            cursor.close()
            conn.close()
            print("취향 프로필 업데이트 완료")
        else:
            print("취향 프로필 생성 실패: 데이터 부족")
    except Exception as e:
        print(f"취향 프로필 업데이트 실패: {e}")

    return {"success": True, "message": f"총 {len(extracted_items)}개 추출 완료", "data": extracted_items}

# [API 2] 취향 프로필 자동 생성
@app.post("/api/generate-taste")
def generate_taste_profile():
    try:
        # 피드에 아이템이 있는지 확인
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM saved_posts WHERE user_id = '1'")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        if count == 0:
            return {"success": False, "message": "피드에 아이템이 없습니다. 먼저 아이템을 추가해 주세요."}
        summary = analyze_vibe(user_id=1)  
        if not summary:
            return {"success": False, "message": "취향 분석에 실패했습니다."}
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO taste_profile (id, summary, updated_at) VALUES (1, %s, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP",
            (summary,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"취향 분석 실패: {str(e)}")

# [API 3] 에이전틱 큐레이션 검색
@app.post("/api/agent-search")
def run_agentic_search(request: SearchRequest):
    try:
        agent = VibeSearchAgent(user_id=1)
        final_answer = agent.run(request.query)
        return {"success": True, "result": final_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에이전트 검색 실패: {str(e)}")

# [API 4] 피드백 저장
@app.post("/api/agentic-search/feedback")
def save_agent_feedback(request: FeedbackRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS search_feedback (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        query TEXT,
        result TEXT,
        feedback_type TEXT,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    """)
    try:
        cursor.execute(
            "INSERT INTO search_feedback (user_id, query, result, feedback_type, reason) VALUES (%s, %s, %s, %s, %s)",
            (str(request.user_id), request.query, request.result, request.feedback_type, request.reason)
        )
        conn.commit()

        # 피드백 저장 후 취향 프로필 업데이트
        try:
            summary = analyze_vibe(user_id=int(request.user_id))
            if summary:
                cursor.execute(
                    "INSERT INTO taste_profile (id, summary, updated_at) VALUES (1, %s, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP",
                    (summary,)
                )
                conn.commit()
        except Exception as e:
            print(f"취향 프로필 업데이트 실패: {e}")

        return {"success": True, "message": "Feedback saved successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# [API 5] 수동 저장
@app.post("/api/items/manual")
def save_manual_item(request: ManualItemCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO saved_posts (user_id, source_url, category, vibe_text, facts, reviews, title, image_url) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                str(request.user_id), 
                request.url, 
                request.category, 
                request.vibe, 
                json.dumps(request.facts, ensure_ascii=False),
                json.dumps(request.facts.get("reviews", {}), ensure_ascii=False), 
                request.facts.get("title", "Manual Item"),
                request.image_url or ""
            )
        )
        conn.commit()

        # 수동 저장 후 취향 프로필 업데이트
        try:
            summary = analyze_vibe(user_id=int(request.user_id))
            if summary:
                cursor.execute(
                    "INSERT INTO taste_profile (id, summary, updated_at) VALUES (1, %s, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP",
                    (summary,)
                )
                conn.commit()
        except Exception as e:
            print(f"취향 프로필 업데이트 실패: {e}")

        return {"success": True, "message": "에이전트 검색 결과가 내 피드에 박제되었습니다."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"수동 저장 실패: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ==========================================
# 일반 CRUD 엔드포인트
# ==========================================
@app.get("/api/items")
def get_items(user_id: str = "1"):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT 
                id, 
                source_url as url, 
                category, 
                facts, 
                vibe_text as vibe, 
                image_url, 
                summary_text, 
                reviews,
                created_at 
            FROM saved_posts 
            WHERE user_id = %s OR user_id = 'default_user'
            ORDER BY created_at DESC
        """
        cursor.execute(query, (user_id,))
        items = cursor.fetchall()
        print(f"프론트로 보내는 아이템 수: {len(items)}")
        return jsonable_encoder(items)
    except Exception as e:
        print(f" 조회 에러: {e}")
        return []
    finally:
        conn.close()

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_posts WHERE id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True}

@app.get("/api/taste")
def get_taste():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM taste_profile WHERE id = 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row if row else {"summary": ""}

@app.get("/api/debug/dist")
def debug_dist():
    import os
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
    uvicorn.run(app, host="0.0.0.0", port=port)