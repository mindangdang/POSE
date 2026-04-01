import json
from collections.abc import AsyncGenerator

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


async def get_db_connection(pool: AsyncConnectionPool | None) -> AsyncGenerator:
    if pool is None:
        raise HTTPException(status_code=500, detail="Database pool is not initialized")

    conn = await pool.getconn()
    try:
        yield conn
    finally:
        await pool.putconn(conn)


async def delete_saved_post_by_id(conn, item_id: int) -> None:
    async with conn.cursor() as cursor:
        await cursor.execute("DELETE FROM saved_posts WHERE id = %s", (item_id,))


async def create_processing_item(conn, user_id: str, post_url: str) -> int:
    async with conn.cursor() as cursor:
        await cursor.execute(
            """
            INSERT INTO saved_posts (user_id, source_url, category, title, vibe_text, image_url, facts)
            VALUES (%s, %s, 'PROCESSING ', '분석 중...', 'AI가 열심히 바이브를 추출하고 있어요', '', '{}')
            RETURNING id
            """,
            (user_id, post_url),
        )
        new_item_id = (await cursor.fetchone())[0]
        await conn.commit()
        return new_item_id


async def count_saved_posts(conn, user_id: str) -> int:
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute("SELECT COUNT(*) AS count FROM saved_posts WHERE user_id = %s", (user_id,))
        row = await cursor.fetchone()
        return row["count"] if row else 0


async def get_latest_taste_summary(conn) -> str | None:
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            "SELECT summary FROM taste_profile WHERE id = 1 ORDER BY updated_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row["summary"] if row else None


async def upsert_taste_profile(conn, summary: str) -> None:
    async with conn.cursor() as cursor:
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
        await conn.commit()


async def create_manual_item(
    conn,
    user_id: str,
    url: str,
    category: str,
    vibe: str,
    facts: dict,
    image_url: str = "",
) -> None:
    async with conn.cursor() as cursor:
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
        await conn.commit()


async def fetch_items(conn, user_id: str):
    async with conn.cursor(row_factory=dict_row) as cursor:
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


async def fetch_taste_profile(conn):
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute("SELECT * FROM taste_profile WHERE id = 1")
        row = await cursor.fetchone()
        return row if row else {"summary": ""}
