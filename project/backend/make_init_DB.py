import asyncio
import os
import psycopg
from dotenv import load_dotenv

# 환경 변수 로드 (.env)
load_dotenv()

DATABASE_URL = os.environ.get("NEON_DB_URL")

async def init_db():
    if not DATABASE_URL:
        print("Error: DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        return

    print("데이터베이스 연결 중...")
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            print("users 테이블 생성 중...")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255),
                    profile_image TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("users 테이블 생성 완료!")
        await conn.commit()

if __name__ == "__main__":
    asyncio.run(init_db())