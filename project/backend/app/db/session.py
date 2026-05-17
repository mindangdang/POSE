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
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        source_url TEXT,
                        title TEXT,
                        category TEXT,
                        image_url TEXT,
                        recommend TEXT,
                        image_vector vector(768),
                        facts JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(source_url, title)
                    );
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS taste_profile (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        summary TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT one_row CHECK (id = 1)
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
            yield conn
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
