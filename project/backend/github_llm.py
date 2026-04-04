import os
from openai import OpenAI
from google import genai
from google.genai import types
from project.backend.config import load_backend_env

def llm_model(kind):
    load_backend_env()
    if kind == 'gemini':
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(".env 파일에 GOOGLE_API_KEY가 설정되지 않았습니다.")

        my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                base_url=my_proxy_url
            )
        )
        return client
    
    elif kind == 'llama':
        token = os.environ.get("GITHUB_TOKEN") 

        client = OpenAI(
            base_url="https://models.inference.ai.azure.com", # GitHub Models 엔드포인트
            api_key=token,
        )
        return client
