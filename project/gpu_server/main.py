from fastapi import FastAPI
from project.gpu_server.routes import routes

app = FastAPI(
    title="POSE GPU Server",
    description="이미지 임베딩 추출 및 리랭킹을 처리하는 GPU 전용 API 서버입니다.",
    version="1.0.0"
)
app.include_router(routes)

@app.get("/health", tags=["health"])
async def health_check():
    """GPU 서버 헬스 체크 엔드포인트"""
    return {"status": "ok", "message": "GPU Server is running"}