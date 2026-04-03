import traceback

from fastapi import APIRouter, Depends, HTTPException

from project.backend.app.core.database import get_repos
from project.backend.app.repositories import Repositories
from project.backend.app.services.crawling import DEFAULT_USER_ID
from project.backend.app.services.taste import build_current_profile, build_summary_text
from project.backend.Step2.preferance_llm import analyze_vibe


router = APIRouter()


@router.post("/generate-taste")
async def generate_taste_profile(repos: Repositories = Depends(get_repos)):
    try:
        count = await repos.saved_posts.count_by_user_id(DEFAULT_USER_ID)
        if count == 0:
            return {"success": False, "message": "피드에 아이템이 없습니다. 먼저 아이템을 추가해 주세요."}

        existing_summary = await repos.taste_profile.get_latest_summary()
        current_profile = build_current_profile(existing_summary)
        summary_dict = await analyze_vibe(user_id=1, current_profile=current_profile)

        if not summary_dict:
            return {"success": False, "message": "취향 분석에 실패했습니다."}

        final_summary_text = build_summary_text(summary_dict)

        try:
            await repos.taste_profile.upsert_summary(final_summary_text)
            print(f"DB 저장 성공: {final_summary_text[:30]}...")
        except Exception as db_exc:
            await repos.taste_profile.conn.rollback()
            print(f"DB 실행 중 에러 발생: {db_exc}")
            raise

        return {"success": True, "summary": final_summary_text}
    except Exception as exc:
        print(f"generate_taste_profile 최종 에러: {exc}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"서버 오류: {exc}") from exc


@router.get("/taste")
async def get_taste(repos: Repositories = Depends(get_repos)):
    try:
        return await repos.taste_profile.get_profile()
    except Exception as exc:
        print(f"취향 프로필 조회 에러: {exc}")
        return {"summary": ""}
