import logging
import re
from typing import Dict
import requests
import json
import os
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# --- 정규식 및 선택자 ---
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")
VIDEO_SELECTOR = "video"
# 인스타그램의 다양한 '다음' 버튼 구조 대응
NEXT_BUTTON_SELECTOR = "button[aria-label*='Next'], button[aria-label*='다음'], div[role='button'] svg[aria-label='다음']"

# 본문 텍스트를 담고 있는 태그 후보군
CAPTION_CANDIDATES = [
    "h1",
    "div._a9zs", 
    "span[dir='auto']",
    "span._ap3a",
]

def crawl_instagram_post(page, post_url: str, max_slides: int = 10) -> Dict[str, object]:
    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "post_type": "image",
        "error": None,
        "blocked": False,
        "requires_login": False,
    }

    try:
        # 페이지 이동 및 로드 대기
        page.goto(post_url, wait_until="domcontentloaded")
        
        try:
            # article이나 main 태그가 뜰 때까지 대기
            page.wait_for_selector("article, main", timeout=15000)
        except PlaywrightTimeoutError:
            page_text = page.content().lower()
            if "login" in page.url or "로그인" in page_text:
                result["requires_login"] = True
                result["error"] = "로그인이 필요하거나 쿠키가 만료되었습니다."
            else:
                result["blocked"] = True
                result["error"] = "접근이 차단되었거나 페이지 구조가 변경되었습니다."
            return result

        # 컨테이너 설정: 화면 전체 탐색을 방지하기 위해 최소한의 기준점(main 또는 article)을 잡습니다.
        if page.locator("article").count() > 0:
            post_container = page.locator("article").first
        else:
            post_container = page.locator("main").first

        # 1. 본문(Caption) 및 해시태그 추출
        for selector in CAPTION_CANDIDATES:
            elements = post_container.locator(selector).all()
            for element in elements:
                if element.is_visible():
                    text = element.inner_text().strip()
                    # 아이디가 아닌 '진짜 본문(15자 이상)'인지 검증
                    if text and not text.startswith("#") and len(text) > 15:
                        result["caption"] = text
                        result["hashtags"] = HASHTAG_PATTERN.findall(text)
                        break
            if result["caption"]:
                break

        # 2. 미디어(이미지/비디오) 추출
        all_images = []
        is_video = False

        for _ in range(max_slides):
            # 화면이 로드되고 슬라이드가 넘어갈 시간을 잠깐 줌
            page.wait_for_timeout(500)
            
            # 비디오 여부 체크
            if post_container.locator(VIDEO_SELECTOR).count() > 0:
                is_video = True
            
            # 1. e.closest('a') === null : 부모 중 <a> 태그가 있는 '추천 게시물 썸네일' 완벽 차단
            # 2. e.clientWidth > 250 : 화면상 가로 너비가 250px 이하인 '프로필, 아이콘' 완벽 차단
            images = post_container.locator("img").evaluate_all(
                """elements => elements
                    .filter(e => e.closest('a') === null)
                    .filter(e => e.clientWidth > 250)
                    .map(e => e.src)
                """
            )
            
            for src in images:
                if not src: continue
                # 인스타그램 실제 사진 서버(CDN) 도메인인지 최종 확인
                if "cdninstagram.com" in src or "fbcdn.net" in src:
                    all_images.append(src)

            # 다음 슬라이드 버튼 찾기 및 클릭
            next_btn = post_container.locator(NEXT_BUTTON_SELECTOR).first
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(1000) # 슬라이드 애니메이션 대기
            else:
                # 더 이상 다음 버튼이 없으면 반복문 종료
                break

        # 중복된 이미지 URL 제거 (순서는 그대로 유지)
        result["image_urls"] = list(dict.fromkeys(all_images))

        # 게시물 타입(Carousel, Video, Image) 판별
        if is_video:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except Exception as e:
        logger.exception(f"크롤링 중 예외 발생: {e}")
        result["error"] = str(e)

    return result

def download_images(image_urls: list, save_dir: str = "insta_vibes"):
    if not image_urls:
        return [] # 빈 리스트 반환으로 수정

    # 폴더가 없으면 생성
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    downloaded_paths = [] # 성공한 파일들의 경로를 담을 바구니

    for index, url in enumerate(image_urls):
        try:
            # 이미지 데이터 가져오기 (requests 사용)
            response = requests.get(url, timeout=10)
            response.raise_for_status() 

            # 파일명 지정 (예: image_01.jpg)
            file_name = f"image_{index + 1:02d}.jpg"
            file_path = os.path.join(save_dir, file_name)

            # 파일로 저장 (바이너리 쓰기 모드 'wb')
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            downloaded_paths.append(file_path) 

        except Exception as e:
            print(f"{index + 1}번째 이미지 다운로드 실패: {e}")
    
    return downloaded_paths