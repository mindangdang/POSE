import os
from project.backend.app.manage.settings import load_backend_env
import httpx

load_backend_env()
api_key = os.environ.get("GOOGLE_API_KEY")
GPU_SERVER_URL = os.environ.get("GPU_SERVER_URL")

if not api_key:
    raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

if not GPU_SERVER_URL:
    raise ValueError(".env 파일에 GPU_SERVER_URL이 설정되지 않았습니다.")

async def _extract_vector_sync(image_url: str):
    payload = {"image_url": image_url}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GPU_SERVER_URL}/embedding", json=payload, timeout=15.0)
        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return
        image_vector = response.json().get("vector")
        if not image_vector:
            return
        return image_vector
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        return


