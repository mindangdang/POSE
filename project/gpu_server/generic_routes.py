from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from project.gpu_server.generic_models import (
    EMBEDDING_MODEL_ID,
    EMBEDDING_MODEL_VERSION,
    EMBEDDING_POOLING_METHOD,
    RERANKER_MODEL_ID,
    generic_models,
)

router = APIRouter()


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)
    normalize: bool = True


class BatchEmbedRequest(BaseModel):
    texts: list[str] = Field(max_length=128)
    normalize: bool = True


class RerankDocument(BaseModel):
    id: str
    text: str = Field(max_length=20000)


class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    documents: list[RerankDocument] = Field(max_length=30)


@router.post("/embed")
async def embed(request: EmbedRequest) -> dict[str, Any]:
    try:
        vectors, _ = await asyncio.to_thread(
            generic_models.embed, request.texts, request.normalize
        )
        dimension = len(vectors[0]) if vectors else 1024
        return {
            "embeddings": vectors,
            "model_id": EMBEDDING_MODEL_ID,
            "model_version": EMBEDDING_MODEL_VERSION,
            "embedding_dimension": dimension,
            "pooling_method": EMBEDDING_POOLING_METHOD,
            "normalized": request.normalize,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding model unavailable: {type(exc).__name__}") from exc


@router.post("/embed/batch")
async def embed_batch(request: BatchEmbedRequest) -> dict[str, Any]:
    if not request.texts:
        return {
            "embeddings": [],
            "model_id": EMBEDDING_MODEL_ID,
            "model_version": EMBEDDING_MODEL_VERSION,
            "embedding_dimension": 1024,
            "pooling_method": EMBEDDING_POOLING_METHOD,
            "normalized": request.normalize,
        }
    results: list[list[float]] = []
    try:
        for start in range(0, len(request.texts), 32):
            batch, _ = await asyncio.to_thread(
                generic_models.embed, request.texts[start : start + 32], request.normalize
            )
            results.extend(batch)
        return {
            "embeddings": results,
            "model_id": EMBEDDING_MODEL_ID,
            "model_version": EMBEDDING_MODEL_VERSION,
            "embedding_dimension": len(results[0]) if results else 1024,
            "pooling_method": EMBEDDING_POOLING_METHOD,
            "normalized": request.normalize,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding model unavailable: {type(exc).__name__}") from exc


@router.post("/rerank")
async def rerank(request: RerankRequest) -> dict[str, Any]:
    documents = [item.model_dump() for item in request.documents]
    try:
        results, _ = await asyncio.to_thread(
            generic_models.rerank, request.query, documents
        )
        return {"results": results, "model_id": RERANKER_MODEL_ID}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Reranker unavailable: {type(exc).__name__}") from exc


@router.get("/model-health")
async def model_health() -> dict[str, Any]:
    return {"status": "ok", **generic_models.status()}
