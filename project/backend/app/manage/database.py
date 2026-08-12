from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from project.backend.app.db.session import (
    create_db_engine,
    create_session_factory,
)
from project.backend.app.manage.settings import get_settings
from project.backend.app.repositories import Repositories, get_repositories


def get_neon_db_url() -> str:
    db_url = get_settings().neon_db_url
    if not db_url:
        raise RuntimeError("NEON_DB_URL environment variable is not set.")
    return db_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_db_engine(get_neon_db_url())
    session_factory = create_session_factory(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    print("SQLAlchemy DB engine and pool initialized")

    yield

    await engine.dispose()
    print("SQLAlchemy DB engine disposed")


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise RuntimeError("Database session factory is not initialized")
    return session_factory


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory(request)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_repos(session: AsyncSession = Depends(get_db_session)) -> Repositories:
    return get_repositories(session)
