all:
    @just --justfile {{justfile()}} -j 2 run-backend run-frontend

# 백엔드 실행 (8000 포트)
run-backend:
    @echo "백엔드 서버 시작 중... (Port: 8000)"
    python main.py runserver 8000  

# 프론트엔드 실행 (5731 포트)
run-frontend:
    @echo "프론트엔드 서버 시작 중... (Port: 5173)"
    cd project/frontend && npx vite --force -- --port 5173  

stop:
    @echo "기존 프로세스 정리 중..."
    -lsof -ti:8000,5173 | xargs kill -9 2>/dev/null
    @echo "정리 완료."  