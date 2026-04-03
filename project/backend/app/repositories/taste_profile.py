from dataclasses import dataclass
from typing import Any

from psycopg.rows import dict_row


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
