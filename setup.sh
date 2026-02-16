#!/bin/bash
# 에러 발생 시 즉시 중단
set -e

echo "🚀 시스템 라이브러리 및 크롬 설치를 시작합니다..."

# 1. 시스템 업데이트 및 필수 의존성 설치 (문제가 된 libgconf-2-4 제거)
sudo apt-get update
sudo apt-get install -y \
    wget \
    gnupg \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    libu2f-udev \
    libvulkan1

# 2. 구글 크롬 최신 안정판 패키지 다운로드
echo "🌐 크롬 패키지를 다운로드 중..."
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# 3. apt를 사용하여 패키지 설치 (의존성 자동 해결)
echo "📦 크롬 설치를 진행합니다..."
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb

# 4. 설치 후 불필요한 패키지 파일 삭제
rm google-chrome-stable_current_amd64.deb

echo "✅ 크롬 및 필수 라이브러리 설치 완료!"
google-chrome --version