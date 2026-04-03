import os
import psycopg
from project.backend.app.core.settings import load_backend_env

# 1. 환경변수에서 Neon DB 접속 주소 불러오기
load_backend_env()
neon_url = os.environ.get("NEON_DB_URL")

if not neon_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def initialize_database():
    print(" Neon DB에 연결 중입니다...")
    conn = None
    cursor = None
    
    try:
        # DB 연결 및 커서 생성
        conn = psycopg.connect(neon_url)
        cursor = conn.cursor()

        # 1. 벡터 검색을 위한 pgvector 확장 프로그램 활성화
        print(" pgvector 확장 프로그램 활성화 중...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # 2. 메인 테이블 생성 (구글 임베딩 모델에 맞춘 768차원)
        print(" saved_posts 테이블 생성 중...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS saved_posts (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            source_url TEXT,
            
            category VARCHAR(20),
            summary_text TEXT,
            
            vibe_text TEXT,
            vibe_vector VECTOR(768), 
            
            facts JSONB,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)

        # 3. 사실 정보(위치, 가격 등) 고속 검색을 위한 GIN 인덱스 생성
        print(" facts 데이터 고속 검색 인덱스(GIN) 생성 중...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_gin ON saved_posts USING GIN (facts);")

        # 작업 확정
        conn.commit()
        print("데이터베이스 스키마 세팅이 완벽하게 완료되었습니다!")

    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
            
    finally:
        # 연결 안전하게 종료
        if cursor: cursor.close()
        if conn: conn.close()
        print(" DB 연결을 종료했습니다.")

if __name__ == "__main__":
    initialize_database()
