import logging
import re
import time
from typing import Dict, List

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#.,!?;:]+)")

CAPTION_CANDIDATES = (
    "article h1._ap3a",
    "article span._ap3a",
    "div._a9zs span",
)


def _unique_ordered(items: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _extract_caption(driver) -> str:
    for selector in CAPTION_CANDIDATES:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            text = element.text.strip()
            if text:
                return text
    return ""


def crawl_instagram_post(driver, post_url: str, timeout: int = 15) -> Dict[str, object]:
    if not post_url:
        raise ValueError("post_url is required")

    driver.get(post_url)
    wait = WebDriverWait(driver, timeout)

    result = {
        "post_url": post_url,
        "caption": "",
        "hashtags": [],
        "image_urls": [],
        "post_type": "image",
    }

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article")))

        caption = _extract_caption(driver)
        result["caption"] = caption
        result["hashtags"] = HASHTAG_PATTERN.findall(caption)

        img_urls = []
        is_video = False
        max_slides = 10

        for _ in range(max_slides):
            images = driver.find_elements(
                By.CSS_SELECTOR,
                "article img[style*='object-fit: cover'], article img._a6_p",
            )
            for img in images:
                src = img.get_attribute("src")
                if src and "cdninstagram.com" in src:
                    img_urls.append(src)

            if driver.find_elements(By.CSS_SELECTOR, "article video"):
                is_video = True

            try:
                next_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[aria-label*='다음'], button[aria-label*='Next']",
                )
                next_btn.click()
                time.sleep(0.8)
            except WebDriverException:
                break

        result["image_urls"] = _unique_ordered(img_urls)

        if is_video:
            result["post_type"] = "video"
        elif len(result["image_urls"]) > 1:
            result["post_type"] = "carousel"

    except TimeoutException as exc:
        logger.warning("Timed out waiting for Instagram post: %s", post_url)
        result["error"] = f"Timeout while loading post: {exc}"
    except WebDriverException as exc:
        logger.exception("WebDriver error while crawling Instagram post: %s", post_url)
        result["error"] = f"WebDriver error: {exc}"

    return result
