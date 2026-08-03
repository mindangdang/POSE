import psycopg

neon_db_url = 'postgresql://neondb_owner:npg_Dro4bCcG1Ikd@ep-curly-base-aii29p7u-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

if not neon_db_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def initialize_database():
    print(" Neon DB에 연결 중입니다...")
    conn = None
    cursor = None
    
    try:
        conn = psycopg.connect(neon_db_url)
        cursor = conn.cursor()
        print(" pgvector 확장 프로그램 활성화 중...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        print(" product_db 테이블 생성 중...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS product_db (
            item_id SERIAL PRIMARY KEY,
            source_url TEXT,
            title TEXT,
            title_vector VECTOR(768),
            price TEXT,
            brand TEXT,
            category VARCHAR(20),
            is_soldout TEXT,
            image_url TEXT,
            image_vector VECTOR(768), 
            shop TEXT,
            gender TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_url, title)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("데이터베이스 스키마 세팅이 완벽하게 완료되었습니다!")

    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
            if cursor:
                cursor.close()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        print(" DB 연결을 종료했습니다.")

if __name__ == "__main__":
    initialize_database()