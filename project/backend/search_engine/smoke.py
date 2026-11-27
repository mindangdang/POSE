from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import SearchRequest
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.main import app as backend_app
from project.gpu_server.main import app as model_server_app

import project.backend.app.manage.database as database_module


class NoopModelServer:
    async def embed(self, texts):
        return None

    async def rerank(self, query, documents):
        return None


async def _run() -> None:
    response = await SearchPipeline(
        provider=FixtureSearchProvider(),
        use_llm=False,
        model_client=NoopModelServer(),
    ).run(SearchRequest(query="quiet study cafe"), user_id="smoke")
    if response.status != "completed" or not (response.verified_results or response.unverified_results):
        raise SystemExit(f"Fixture smoke failed: status={response.status}")
    with patch.object(database_module, "get_settings", lambda: SimpleNamespace(neon_db_url=None)):
        with TestClient(backend_app) as backend_client:
            backend_health = backend_client.get("/api/v2/health")
        with TestClient(model_server_app) as model_client:
            model_health = model_client.get("/health")
    if backend_health.status_code != 200 or model_health.status_code != 200:
        raise SystemExit("Backend or lazy model-server health check failed")
    print(
        f"Fixture smoke passed: status={response.status}, "
        f"verified={len(response.verified_results)}, "
        f"unverified={len(response.unverified_results)}, "
        "backend/model-server health=ok"
    )


if __name__ == "__main__":
    asyncio.run(_run())
