import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Ollama MCP Tutor"
    # Ollama는 기본적으로 로컬호스트 11434 포트를 사용합니다.
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_API_KEY: str = "ollama"  # Ollama는 키가 필요 없지만 SDK 호환성을 위해 더미 값 입력
    # Codespaces CPU 환경을 고려해 가벼운 모델 권장 (llama3.2, mistral, phi4 등)
    MODEL_NAME: str = "llama3.2" 
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()