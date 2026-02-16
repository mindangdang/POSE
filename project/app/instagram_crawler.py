import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")
ARTICLE_SELECTOR = "article"
VIDEO_SELECTOR = "article video"
MEDIA_IMAGE_SELECTOR = "article img[decoding='auto'], article img[crossorigin='anonymous'], article img"
NEXT_BUTTON_SELECTOR = "button[aria-label*='Next'], button[aria-label*='다음']"
META_DESC_SELECTOR = "meta[property='og:description']"
LOGIN_INDICATOR_SELECTOR = "form input[name='username'], form#loginForm"
BLOCK_INDICATOR_SELECTOR = "iframe[title*='captcha'], div[role='dialog']"

# 클래스 난독화 변경에 대비해 일반 태그/메타 순서로 fallback
CAPTION_CANDIDATES: Sequence[str] = (
    "article h1",
    "article span[dir='auto']",
    "article span._ap3a",
    "div._a9zs span",
)

DEFAULT_MAX_SLIDES = 10
DEFAULT_TIMEOUT = 12
DEFAULT_TRANSITION_TIMEOUT = 2
INITIAL_PAGE_SIGNAL_TIMEOUT = 2


def _unique_ordered(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _is_valid_post_url(post_url: str) -> bool:
    return isinstance(post_url, str) and "instagram.com" in post_url and "/p/" in post_url


def _build_result(post_url: str) -> Dict[str, object]:
    return {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "post_type": "image",
        "error": None,
        "blocked": False,
        "requires_login": False,
    }


def _detect_access_barrier(driver: WebDriver) -> Optional[str]:
    current_url = (driver.current_url or "").lower()
    if "/accounts/login" in current_url:
        return "login_required"
    if driver.find_elements(By.CSS_SELECTOR, LOGIN_INDICATOR_SELECTOR):
        return "login_required"

    page_source = (driver.page_source or "").lower()
    if "challenge_required" in page_source or "captcha" in page_source:
        return "blocked"
    if driver.find_elements(By.CSS_SELECTOR, BLOCK_INDICATOR_SELECTOR):
        return "blocked"
    return None


def _wait_for_initial_page_signal(driver: WebDriver, timeout: int) -> Tuple[bool, Optional[str]]:
    """Wait for either post article or a barrier signal right after page load.

    Returns:
        (article_found, barrier)
    """
    if timeout <= 0:
        return False, _detect_access_barrier(driver)

    def _initial_signal(d: WebDriver):
        barrier = _detect_access_barrier(d)
        if barrier:
            return (False, barrier)
        if d.find_elements(By.CSS_SELECTOR, ARTICLE_SELECTOR):
            return (True, None)
        return False

    try:
        return WebDriverWait(driver, timeout).until(_initial_signal)
    except TimeoutException:
        return False, _detect_access_barrier(driver)


def _extract_caption_from_dom(driver: WebDriver) -> str:
    for selector in CAPTION_CANDIDATES:
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            text = (element.text or "").strip()
            if text and not text.startswith("#"):
                return text
    return ""


def _extract_caption_from_meta(driver: WebDriver) -> str:
    metas = driver.find_elements(By.CSS_SELECTOR, META_DESC_SELECTOR)
    for meta in metas:
        content = (meta.get_attribute("content") or "").strip()
        if content:
            # "username on Instagram: \"caption\""
            if ":" in content:
                content = content.split(":", 1)[1].strip()
            return content.strip('"')
    return ""


def _extract_caption(driver: WebDriver) -> str:
    caption = _extract_caption_from_dom(driver)
    if caption:
        return caption
    return _extract_caption_from_meta(driver)


def _extract_image_urls(driver: WebDriver) -> List[str]:
    urls: List[str] = []
    for img in driver.find_elements(By.CSS_SELECTOR, MEDIA_IMAGE_SELECTOR):
        src = img.get_attribute("src")
        if src and "cdninstagram.com" in src:
            urls.append(src)
    return _unique_ordered(urls)


def _has_video(driver: WebDriver) -> bool:
    return bool(driver.find_elements(By.CSS_SELECTOR, VIDEO_SELECTOR))


def _find_next_button(driver: WebDriver) -> Optional[WebElement]:
    for button in driver.find_elements(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR):
        try:
            if button.is_displayed() and button.is_enabled():
                return button
        except WebDriverException:
            continue
    return None


def _wait_for_slide_change(driver: WebDriver, previous_images: List[str], timeout: int) -> None:
    if timeout <= 0:
        return

    WebDriverWait(driver, timeout).until(
        lambda d: (
            _extract_image_urls(d) != previous_images
            or _has_video(d)
            or _find_next_button(d) is None
        )
    )


def _crawl_media(driver: WebDriver, wait: WebDriverWait, max_slides: int) -> Dict[str, object]:
    all_images: List[str] = []
    is_video = False

    for _ in range(max_slides):
        current_images = _extract_image_urls(driver)
        all_images.extend(current_images)
        is_video = is_video or _has_video(driver)

        next_button = _find_next_button(driver)
        if not next_button:
            break

        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)))
            next_button.click()
            _wait_for_slide_change(driver, current_images, DEFAULT_TRANSITION_TIMEOUT)
        except TimeoutException:
            # 이미지 URL 변화가 없거나 비디오 슬라이드인 경우가 있어 빠르게 종료
            logger.debug("Slide transition wait timed out; stopping further navigation.")
            break
        except WebDriverException:
            logger.debug("Failed to move to next slide.", exc_info=True)
            break

    return {
        "image_urls": _unique_ordered(all_images),
        "has_video": is_video,
    }


def crawl_instagram_post(
    driver: WebDriver,
    post_url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_slides: int = DEFAULT_MAX_SLIDES,
) -> Dict[str, object]:

    if not post_url:
        raise ValueError("post_url is required")
    if not _is_valid_post_url(post_url):
        raise ValueError("post_url must be a valid Instagram post URL")
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    if max_slides <= 0:
        raise ValueError("max_slides must be greater than 0")

    result = _build_result(post_url)

    try:
        driver.get(post_url)
        wait = WebDriverWait(driver, timeout)

        article_found, barrier = _wait_for_initial_page_signal(driver, INITIAL_PAGE_SIGNAL_TIMEOUT)
        if barrier == "login_required":
            result["requires_login"] = True
            result["error"] = "Instagram login is required or session is not authenticated"
            return result
        if barrier == "blocked":
            result["blocked"] = True
            result["error"] = "Instagram blocked automated access (challenge/captcha)"
            return result

        if not article_found:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ARTICLE_SELECTOR)))

        caption = _extract_caption(driver)
        result["caption"] = caption
        result["hashtags"] = HASHTAG_PATTERN.findall(caption)

        media = _crawl_media(driver, wait, max_slides)
        result["image_urls"] = media["image_urls"]

        if media["has_video"]:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except TimeoutException as exc:
        logger.warning("Timed out while crawling Instagram post: %s", post_url)
        result["error"] = f"Timeout while loading post: {exc}"
    except WebDriverException as exc:
        logger.exception("WebDriver error while crawling Instagram post: %s", post_url)
        result["error"] = f"WebDriver error: {exc}"
    except Exception as exc:
        logger.exception("Unexpected crawler error for post: %s", post_url)
        result["error"] = f"Unexpected error: {exc}"

    return result


def build_chrome_stealth_args(proxy: Optional[str] = None, user_agent: Optional[str] = None) -> List[str]:
    args = [
        "--headless=new",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1280,1696",
        "--lang=ko-KR,ko,en-US,en",
    ]
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    if proxy:
        args.append(f"--proxy-server={proxy}")
    return args


def apply_runtime_stealth(driver: WebDriver) -> None:

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                    Object.defineProperty(navigator, 'language', {get: () => 'ko-KR'});
                """
            },
        )
    except Exception:
        logger.debug("CDP stealth script injection is not available for this driver.", exc_info=True)