import uvicorn
import os

if __name__ == "__main__":
    # 포트 8000번 사용
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)