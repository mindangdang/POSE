#!/bin/bash
# 윈도우 줄바꿈(CRLF) 문제가 생겨도 강제로 무시하도록 설정
set -e

echo "🚀 시스템 라이브러리 및 크롬 설치를 시작합니다..."

sudo apt-get update
sudo apt-get install -y wget gnupg curl libnss3 libgconf-2-4 libfontconfig1 libxcb1 libgbm-dev

# 최신 보안 정책(apt-key 대신 keyring 사용)을 적용한 크롬 설치법 🌟
curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list

sudo apt-get update
sudo apt-get install -y google-chrome-stable

echo "✅ 크롬 및 필수 라이브러리 설치 완료!"