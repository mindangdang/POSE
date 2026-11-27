from contextlib import asynccontextmanager

from fastapi import FastAPI
from project.gpu_server.routes import router
from project.gpu_server.generic_routes import router as generic_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # The legacy FashionSigLIP model and generic BGE models load only on first use.
    yield

app = FastAPI(
    title="POSE GPU Server",
    description="POSE generic text embedding and reranking; legacy image embedding remains isolated.",
    version="2.0.0",
    lifespan=lifespan
)
app.include_router(router)
app.include_router(generic_router)

@app.get("/health", tags=["health"])
async def health_check():
    """Health check without loading any machine-learning weights."""
    from project.gpu_server.generic_models import generic_models

    return {"status": "ok", "service": "POSE model server", **generic_models.status()}
