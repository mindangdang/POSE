#!/bin/bash

echo "🚀 Setting up Ollama MCP Environment..."

# 1. 의존성 설치
pip install -r requirements.txt

# 2. Ollama 설치 (없는 경우)
if ! command -v ollama &> /dev/null
then
    echo "⬇️ Installing Ollama..."
    curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh
else
    echo "✅ Ollama already installed."
fi

# 3. Ollama 서버 백그라운드 실행
echo "🧠 Starting Ollama Server..."
ollama serve &
OLLAMA_PID=$!

# 서버가 뜰 때까지 잠시 대기
sleep 5

# 4. 모델 다운로드 (llama3.2:3b 추천 - 가볍고 빠름)
# Codespaces에서는 큰 모델(8b 이상)은 매우 느립니다.
MODEL="llama3.2"
echo "📥 Pulling Model: $MODEL..."
ollama pull $MODEL

# 5. FastAPI 서버 실행
echo "✨ Starting MCP Server..."
python main.py

# 스크립트 종료 시 Ollama도 종료
kill $OLLAMA_PID