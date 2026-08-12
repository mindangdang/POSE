import httpx
from project.backend.app.manage.settings import get_settings
from typing import Optional, List

GPU_SERVER_URL = get_settings().gpu_server_url

if not GPU_SERVER_URL:
    raise ValueError(
        ".env 파일에 GPU_SERVER_URL이 설정되지 않았습니다. 접속 주소를 확인해주세요."
    )

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


async def _extract_vector_batch(image_urls: list[str], client: Optional[httpx.AsyncClient] = None) -> List:
    # 1. 페이로드 키 변경: image_url -> image_urls
    payload = {"image_urls": image_urls}
    
    # 커넥션 풀링을 위해 외부에서 주입받은 client 우선 사용
    _client = client or httpx.AsyncClient()
    
    try:
        # 2. 엔드포인트 변경 및 Timeout 증가 (다건 이미지 다운로드/추론 대기 시간 확보)
        response = await _client.post(f"{GPU_SERVER_URL}/embedding_batch", json=payload, timeout=45.0)
        
        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return [None] * len(image_urls)
            
        # 3. 반환 키 변경: vector -> vectors
        vectors = response.json().get("vectors")
        if not vectors:
            return [None] * len(image_urls)
            
        return vectors
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        # 4. 에러 발생 시 입력 길이와 동일한 배열 반환
        return [None] * len(image_urls)
        
    finally:
        if client is None:
            await _client.aclose()


async def _extract_text_vector_batch(texts: list[str], client: Optional[httpx.AsyncClient] = None) -> List:
    # 1. 페이로드 키 변경: text -> texts
    payload = {"texts": texts}
    
    _client = client or httpx.AsyncClient()
    
    try:
        # 2. 엔드포인트 변경 및 Timeout 증가
        response = await _client.post(f"{GPU_SERVER_URL}/encode_text_batch", json=payload, timeout=30.0)
        
        if response.status_code != 200:
            print(f"GPU 서버 연산 에러: {response.text}")
            return [None] * len(texts)
            
        # 3. 반환 키 변경: vector -> vectors
        vectors = response.json().get("vectors")
        if not vectors:
            return [None] * len(texts)
            
        return vectors
    
    except Exception as e:
        print(f"GPU 서버 통신 에러: {e}")
        return [None] * len(texts)
        
    finally:
        if client is None:
            await _client.aclose()
