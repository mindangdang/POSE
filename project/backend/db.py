import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from psycopg import InterfaceError, OperationalError

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


async def init_db(db_pool: AsyncConnectionPool) -> None:
    """비동기 방식으로 DB 테이블 스키마를 초기화"""
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
                        summary_text TEXT,
                        image_url TEXT,
                        vibe_text TEXT,
                        vibe_vector vector(768),
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
    except Exception as e:
        print(f"DB 초기화 중 경고: {e}")


def create_db_pool(conninfo: str, min_size: int = 5, max_size: int = 20) -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=conninfo, min_size=min_size, max_size=max_size)


async def _ping_connection(conn: Any) -> None:
    # Serverless DB는 idle 이후 기존 connection이 stale 상태가 될 수 있어서,
    # 풀에서 꺼낸 직후 가벼운 ping으로 실제 연결 가능 여부를 확인한다.
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
        except (OperationalError, InterfaceError) as e:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass

            if recreate_pool is None or attempt == 1:
                raise HTTPException(status_code=500, detail=f"Database connection is unavailable: {e}") from e

            current_pool = await recreate_pool()
        finally:
            if conn is not None and not getattr(conn, "closed", False):
                await pool_used.putconn(conn)

    raise HTTPException(status_code=500, detail="Database connection is unavailable")


@dataclass(slots=True)
class SavedPostsRepository:
    conn: Any

    async def delete_by_id(self, item_id: int) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM saved_posts WHERE id = %s", (item_id,))

    async def create_processing_item(self, user_id: str, post_url: str) -> int:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (user_id, source_url, category, title, vibe_text, image_url, facts)
                VALUES (%s, %s, 'PROCESSING ', '분석 중...', 'AI가 열심히 바이브를 추출하고 있어요', '', '{}')
                RETURNING id
                """,
                (user_id, post_url),
            )
            new_item_id = (await cursor.fetchone())[0]
            await self.conn.commit()
            return new_item_id

    async def count_by_user_id(self, user_id: str) -> int:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT COUNT(*) AS count FROM saved_posts WHERE user_id = %s", (user_id,))
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def create_manual_item(
        self,
        user_id: str,
        url: str,
        category: str,
        vibe: str,
        facts: dict,
        image_url: str = "",
    ) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO saved_posts (user_id, source_url, category, vibe_text, facts, title, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    url,
                    category,
                    vibe,
                    json.dumps(facts),
                    facts.get("title", "Manual Item"),
                    image_url,
                ),
            )
            await self.conn.commit()

    async def list_feed_items(self, user_id: str):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    id,
                    source_url as url,
                    category,
                    facts,
                    vibe_text as vibe,
                    image_url,
                    summary_text,
                    created_at
                FROM saved_posts
                WHERE user_id = %s OR user_id = 'default_user'
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            items = await cursor.fetchall()
            return jsonable_encoder(items)


@dataclass(slots=True)
class TasteProfileRepository:
    conn: Any

    async def get_latest_summary(self) -> str | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                "SELECT summary FROM taste_profile WHERE id = 1 ORDER BY updated_at DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            return row["summary"] if row else None

    async def upsert_summary(self, summary: str) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO taste_profile (id, summary, updated_at)
                VALUES (1, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id)
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (summary,),
            )
            await self.conn.commit()

    async def get_profile(self):
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM taste_profile WHERE id = 1")
            row = await cursor.fetchone()
            return row if row else {"summary": ""}


@dataclass(slots=True)
class Repositories:
    saved_posts: SavedPostsRepository
    taste_profile: TasteProfileRepository


def get_repositories(conn: Any) -> Repositories:
    return Repositories(
        saved_posts=SavedPostsRepository(conn),
        taste_profile=TasteProfileRepository(conn),
    )
