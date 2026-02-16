#!/bin/bash

echo "🚀 시스템 라이브러리 및 크롬 설치를 시작합니다..."

# 패키지 목록 업데이트 및 필수 라이브러리 설치
sudo apt-get update
sudo apt-get install -y wget gnupg libnss3 libgconf-2-4 libfontconfig1 libxcb1 libgbm-dev

# 구글 크롬 설치
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
sudo apt-get update
sudo apt-get install -y google-chrome-stable

echo "✅ 크롬 및 필수 라이브러리 설치 완료!"