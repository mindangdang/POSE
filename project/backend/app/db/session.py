from collections.abc import AsyncGenerator
from typing import Any, Awaitable, Callable
from fastapi import HTTPException
from psycopg import InterfaceError, OperationalError
from psycopg_pool import AsyncConnectionPool

async def init_db(db_pool: AsyncConnectionPool) -> None:
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saved_posts (
                        item_id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        source_url TEXT,
                        title TEXT,
                        price TEXT,
                        brand TEXT,
                        category TEXT,
                        is_available TEXT,
                        image_url TEXT,
                        image_vector vector(768),
                        shop TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(source_url, title)
                    );
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS taste_profile (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT UNIQUE NOT NULL,
                        summary TEXT,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS event_logs (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        user_id TEXT,
                        session_id TEXT NOT NULL,
                        event_name TEXT NOT NULL,
                        properties JSONB NOT NULL DEFAULT '{}'::jsonb,
                        page TEXT,
                        user_agent TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                await conn.commit()
        print("DB 테이블 초기화 완료")
    except Exception as exc:
        print(f"DB 초기화 중 경고: {exc}")

def create_db_pool(conninfo: str, min_size: int = 5, max_size: int = 20) -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=conninfo, min_size=min_size, max_size=max_size)

async def _ping_connection(conn: Any) -> None:
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT 1")
        await cursor.fetchone()

async def get_db_connection(
    pool: AsyncConnectionPool | None,
    recreate_pool: Callable[[], Awaitable[AsyncConnectionPool]] | None = None,
) -> AsyncGenerator[Any, None]:
    current_pool = pool

    for attempt in range(2):
        if current_pool is None or current_pool.closed:
            if recreate_pool is None:
                raise HTTPException(status_code=500, detail="Database pool is not initialized")
            current_pool = await recreate_pool()

        conn = None
        pool_used = current_pool
        try:
            conn = await pool_used.getconn()
            await _ping_connection(conn)
            try:
                yield conn
            except Exception:
                if not getattr(conn, "closed", False):
                    await conn.rollback()
                raise
            return
        except (OperationalError, InterfaceError) as exc:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass

            if recreate_pool is None or attempt == 1:
                raise HTTPException(
                    status_code=500,
                    detail=f"Database connection is unavailable: {exc}",
                ) from exc

            current_pool = await recreate_pool()
        finally:
            if conn is not None and not getattr(conn, "closed", False):
                await pool_used.putconn(conn)

    raise HTTPException(status_code=500, detail="Database connection is unavailable")
