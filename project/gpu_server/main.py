from contextlib import asynccontextmanager

from fastapi import FastAPI
from project.gpu_server.embedding_reranking import FashionSiglipReRankingPipeline
from project.gpu_server.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 모듈 임베딩이 아닌 lifespan에서 모델을 로드하여 uvicorn의 초기화 지연 및 타임아웃을 방지합니다.
    print("[gpu_server] Lifecycle: FashionSigLIP 파이프라인 초기화 시작...")
    FashionSiglipReRankingPipeline()
    print("[gpu_server] Lifecycle: 파이프라인 로드 완료.")
    yield

app = FastAPI(
    title="POSE GPU Server",
    description="이미지 임베딩 추출 및 리랭킹을 처리하는 GPU 전용 API 서버입니다.",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(router)

@app.get("/health", tags=["health"])
async def health_check():
    """GPU 서버 헬스 체크 엔드포인트"""
    return {"status": "ok", "message": "GPU Server is running"}