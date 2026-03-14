from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from playwright.sync_api import sync_playwright
from backend.Step1.Rapid_api_crawler import Rapid_crawler
from backend.Step1.instagram_crawler import download_images, crawl_instagram_post
from backend.Step1.image_ocr_llm import extract_fact_and_vibe
from backend.Step1.insert_DB import insert_items_to_db 
from backend.Step1.preference_llm import analyze_vibe
from backend.Step2.main_agent import VibeSearchAgent          

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 로컬 개발용 허용. 실전 배포 시 도메인 지정 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEON_DB_URL = os.environ.get("DATABASE_URL")

def get_db():
    if not NEON_DB_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL environment variable is not set.")
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
        category TEXT,
        summary_text TEXT,
        vibe_text TEXT,
        vibe_vector vector(768),
        facts JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_url, category)
      );
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


# [API 1] 크롤링 & 데이터 추출 (기존 로직)
@app.post("/api/extract-url")
def extract_and_save_url(request: UrlAnalyzeRequest):
    post_url = request.url
    session_id = request.session_id
    rapid_api_key = os.environ.get("RAPIDAPI_KEY")
    
    crawl_result = None
    
    # 크롤러 실행
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

    # 이미지 다운로드 & AI 파이프라인
    downloaded_files = download_images(crawl_result.get("image_urls", []), save_dir="insta_vibes")
    try:
        ai_result = extract_fact_and_vibe(
            image_paths=downloaded_files, 
            caption=crawl_result.get("caption", ""),  
            hashtags=crawl_result.get("hashtags", []) 
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 에러: {str(e)}")

    extracted_items = ai_result.get("extracted_items", [])
    
    # DB 적재
    try:
        user_id = "default_user" 
        insert_items_to_db(user_id, post_url, extracted_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 저장 에러: {str(e)}")

    # 임시 파일 삭제
    for file_path in downloaded_files:
        try: os.remove(file_path)
        except: pass

    return {"success": True, "message": f"총 {len(extracted_items)}개 추출 완료", "data": extracted_items}

# [API 2] 취향 프로필 자동 생성 (preference_llm 연동)
@app.post("/api/generate-taste")
def generate_taste_profile():
    """preference_llm.py의 로직을 호출하여 사용자의 취향을 분석하고 업데이트합니다."""
    try:
        summary = analyze_vibe(user_id="default_user") 
        
        # 분석 결과를 DB에 저장
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

# [API 3] 에이전틱 큐레이션 검색 (main_agent 연동)
@app.post("/api/agent-search")
def run_agentic_search(request: SearchRequest):
    """main_agent.py의 에이전트를 호출하여 Vibe Search 쿼리를 처리합니다."""
    try:
        # main_agent.py 내부에 구현해두신 클래스/함수 호출
        agent = VibeSearchAgent(user_id="default_user")
        
        # 에이전트가 MCP를 거쳐 검색/큐레이션한 최종 마크다운 텍스트 반환
        final_answer = agent.run(request.query)
        
        return {"success": True, "result": final_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에이전트 검색 실패: {str(e)}")

# [API 4] 에이전트 검색 결과 피드백 저장 (Like/Dislike)

@app.post("/api/agentic-search/feedback")
def save_agent_feedback(request: FeedbackRequest):
    """사용자가 에이전트의 검색 결과에 남긴 피드백(학습 데이터)을 DB에 저장합니다."""
    conn = get_db()
    cursor = conn.cursor()
    
    # 피드백을 저장할 테이블이 없다면 동적으로 생성 (init_db에 미리 넣어두면 더 좋습니다)
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
        return {"success": True, "message": "Feedback saved successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")
    finally:
        cursor.close()
        conn.close()

#  [API 5] 에이전트 큐레이션 결과를 내 피드에 수동 저장

@app.post("/api/items/manual")
def save_manual_item(request: ManualItemCreate):
    """사용자가 마음에 든 에이전틱 검색 결과를 자신의 영감 피드(saved_posts)에 강제 저장합니다."""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO saved_posts (user_id, source_url, category, vibe_text, facts) VALUES (%s, %s, %s, %s, %s)",
            (
                str(request.user_id), 
                request.url, 
                request.category, 
                request.vibe, 
                json.dumps(request.facts, ensure_ascii=False)
            )
        )
        conn.commit()
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
def get_items():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM saved_posts ORDER BY created_at DESC")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return items

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

# ==========================================
# 프론트엔드 (React SPA) 서빙
# ==========================================
if os.path.exists("dist"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html")
    return {"error": "Frontend not built. Run 'npm run build' first."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)