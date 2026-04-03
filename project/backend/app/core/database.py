import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request
from psycopg_pool import AsyncConnectionPool

from project.backend.app.core.settings import load_backend_env
from project.backend.app.db.session import (
    create_db_pool,
    get_db_connection as get_pooled_db_connection,
    init_db,
)
from project.backend.app.repositories import Repositories, get_repositories


load_backend_env()


def get_neon_db_url() -> str:
    db_url = os.environ.get("NEON_DB_URL")
    if not db_url:
        raise RuntimeError("NEON_DB_URL environment variable is not set.")
    return db_url


async def rebuild_db_pool(app: FastAPI) -> AsyncConnectionPool:
    old_pool = getattr(app.state, "db_pool", None)
    new_pool = create_db_pool(conninfo=get_neon_db_url(), min_size=5, max_size=20)
    app.state.db_pool = new_pool

    if old_pool is not None and not old_pool.closed:
        try:
            await old_pool.close()
        except Exception as exc:
            print(f"기존 DB 풀 종료 중 경고: {exc}")

    print("DB 커넥션 풀 재생성 완료")
    return new_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_pool = await rebuild_db_pool(app)
    print("DB 커넥션 풀 생성 완료")
    await init_db(db_pool)

    yield

    if getattr(app.state, "db_pool", None) is not None:
        await app.state.db_pool.close()
        print("DB 커넥션 풀 안전하게 종료됨")


async def get_db_connection(request: Request) -> AsyncGenerator[object, None]:
    async for conn in get_pooled_db_connection(
        getattr(request.app.state, "db_pool", None),
        recreate_pool=lambda: rebuild_db_pool(request.app),
    ):
        yield conn


async def get_repos(conn=Depends(get_db_connection)) -> Repositories:
    return get_repositories(conn)
