import logging
import re
from typing import Dict
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# --- 정규식 및 선택자 (인스타그램 최신 DOM 구조에 맞게 수정!) ---
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")
ARTICLE_SELECTOR = "article, main" # article이 없으면 main 태그라도 찾도록 변경
MEDIA_IMAGE_SELECTOR = "img[style*='object-fit'], img[crossorigin='anonymous']" # 더 넓은 범위의 이미지 찾기
VIDEO_SELECTOR = "video"
NEXT_BUTTON_SELECTOR = "button[aria-label*='Next'], button[aria-label*='다음'], div[role='button'] svg[aria-label='다음']"

# 본문 텍스트를 찾는 후보군 (앞에 붙었던 article 뺌)
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
        page.goto(post_url, wait_until="domcontentloaded")
        
        try:
            # 코드스페이스 환경을 고려해 대기 시간을 15초로 넉넉하게 늘림
            page.wait_for_selector(ARTICLE_SELECTOR, timeout=15000)
        except PlaywrightTimeoutError:
            page_text = page.content().lower()
            if "login" in page.url or "로그인" in page_text:
                result["requires_login"] = True
                result["error"] = "로그인이 필요하거나 쿠키가 만료되었습니다."
            else:
                result["blocked"] = True
                result["error"] = "접근이 차단되었거나 페이지 구조가 변경되었습니다."
            
            page.screenshot(path="error_screenshot.png")
            return result

        # 1. 본문(Caption) 추출
        for selector in CAPTION_CANDIDATES:
            # first 대신 all()로 해당되는 요소들을 전부 가져옵니다.
            elements = page.locator(selector).all()
            for element in elements:
                if element.is_visible():
                    text = element.inner_text().strip()
                    # 💡 텍스트가 존재하고, 단순 아이디(길이 15자 이하 등)가 아닌 '진짜 본문'일 때만 저장
                    if text and not text.startswith("#") and len(text) > 15:
                        result["caption"] = text
                        result["hashtags"] = HASHTAG_PATTERN.findall(text)
                        break
            if result["caption"]: # 본문을 찾았으면 바깥 반복문도 종료
                break

        # 2. 미디어(이미지/비디오) 추출
        all_images = []
        is_video = False

        for _ in range(max_slides):
            # 화면이 살짝 로드될 시간을 줌
            page.wait_for_timeout(500)
            
            if page.locator(VIDEO_SELECTOR).count() > 0:
                is_video = True
            
            images = page.locator(MEDIA_IMAGE_SELECTOR).evaluate_all(
                "elements => elements.map(e => e.src)"
            )
            # 인스타그램 이미지 링크만 걸러내기
            valid_images = [src for src in images if "cdninstagram.com" in src or "fbcdn.net" in src]
            all_images.extend(valid_images)

            # 다음 슬라이드 버튼 클릭
            next_btn = page.locator(NEXT_BUTTON_SELECTOR).first
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(1000) # 슬라이드 넘어가는 애니메이션 대기
            else:
                break

        result["image_urls"] = list(dict.fromkeys(all_images))

        if is_video:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except Exception as e:
        logger.exception(f"크롤링 중 예외 발생: {e}")
        result["error"] = str(e)
        page.screenshot(path="exception_screenshot.png")

    return result
