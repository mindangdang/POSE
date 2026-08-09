import psycopg
from project.backend.app.manage.settings import get_settings

# 1. 환경변수에서 Neon DB 접속 주소 불러오기
neon_url = get_settings().neon_db_url

if not neon_url:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

def initialize_database():
    print(" Neon DB에 연결 중입니다...")
    conn = None
    cursor = None
    
    try:
        conn = psycopg.connect(neon_url)
        cursor = conn.cursor()
        print(" pgvector 확장 프로그램 활성화 중...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        print(" saved_posts 테이블 생성 중...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS saved_posts (
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            likes INTEGER NOT NULL DEFAULT 0,
            dislikes INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, product_id),
            CONSTRAINT fk_saved_posts_product_id_product_db
                FOREIGN KEY (product_id) REFERENCES product_db(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_saved_posts_user_id_users
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("데이터베이스 스키마 세팅이 완벽하게 완료되었습니다!")

    except Exception as e:
        print(f" 에러 발생: {e}")
        if conn:
            conn.rollback()
            
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        print(" DB 연결을 종료했습니다.")

if __name__ == "__main__":
    initialize_database()
