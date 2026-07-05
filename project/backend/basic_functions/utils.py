import os
import httpx
from project.backend.app.manage.settings import get_settings

GPU_SERVER_URL = get_settings().gpu_server_url

if not GPU_SERVER_URL:
    raise ValueError(" .env 파일에 NEON_DB_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요.")

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


async def _extract_text_vector_sync(text: str):
    payload = {"text": text}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GPU_SERVER_URL}/encode_text", json=payload, timeout=15.0)
        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return
        text_vector = response.json().get("vector")
        if not text_vector:
            return
        return text_vector
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        return



