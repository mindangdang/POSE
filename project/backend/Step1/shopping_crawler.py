import os
import re
import json
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydantic import BaseModel,Field
from typing import Optional

from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ---안전한 데이터 파싱을 위한 Pydantic 스키마 ---
class ProductFallbackSchema(BaseModel):
    title: str = Field(description="상품의 정확한 이름")
    price: str = Field(description="상품의 가격 (숫자 또는 쉼표 포함)")
    currency: str = Field(description="통화 (예: KRW, USD)")
    image_url: str = Field(
        description="페이지 HTML의 'og:image', 'twitter:image' 또는 메인 상품의 고화질 <img> 태그 절대 경로 URL. 상대 경로는 절대 경로로 변환할 것. placeholder 서비스 절대 금지."
    )
    brand: str = Field(default="", description="상품의 브랜드 이름")
    description: str = Field(default="", description="상품의 상세 설명 요약")

async def fallback_with_gemini(url: str, html_content: str):
    try:
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        truncated_html = html_content[:50000]

        prompt = f"""
        Extract accurate product information from the provided HTML source of {url}.
        If a value cannot be found, leave it empty. DO NOT guess.
        
        [HTML SOURCE]
        {truncated_html}
        """

        print(f"[{url}] Gemini HTML 기반 폴백 분석 시작...")
        
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductFallbackSchema, # Pydantic 스키마 강제
                temperature=0.0 
            )
        )

        data = response.parsed
        
        return {
            "url": url,
            "title": data.title,
            "brand": data.brand,
            "price": data.price,
            "currency": data.currency,
            "image_url": data.image_url,
            "description": data.description,
            "source": "gemini-html-fallback" 
        }
        
    except Exception as e:
        print(f"Gemini 폴백 파싱 실패: {e}")
        return None

# -----------------------------------
WHITESPACE_PATTERN = re.compile(r'\s+')

def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_PATTERN.sub(' ', str(value)).strip()

def _extract_json_ld_products(soup: BeautifulSoup) -> list[dict]:
    products = []
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        raw = script.string
        if not raw: continue
        try:
            payload = json.loads(raw.strip())
            candidates = payload if isinstance(payload, list) else [payload]
            
            for candidate in candidates:
                if not isinstance(candidate, dict): continue
                
                if candidate.get("@type") == "Product":
                    products.append(candidate)
                elif candidate.get("@graph") and isinstance(candidate["@graph"], list):
                    for item in candidate["@graph"]:
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            products.append(item)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
            
    return products

def _extract_meta_content(soup: BeautifulSoup, property_name: str) -> str:
    selector = f'meta[property="{property_name}"], meta[name="{property_name}"], meta[itemprop="{property_name}"]'
    meta = soup.select_one(selector)

    if meta and meta.get('content'):
        return _clean_text(meta['content'])
        
    return ""

async def _load_product_page(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }
    try:
        # HTTP/2 활성화로 헤더 압축 및 다중화 이점 챙기기
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, http2=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
            final_url = str(response.url)

            is_js_heavy = any(domain in url for domain in ["musinsa.com", "kream.co.kr", "zara.com"])
            # <script>는 모든 페이지에 있으므로 판단 기준에서 제외하고, 핵심 메타태그 유무로만 판단
            if is_js_heavy or ("og:title" not in html and "application/ld+json" not in html):
                print(f"[{url}] JS 렌더링 필요. Playwright 가동...")
                raise ValueError("Need JS rendering")

            return {"html": html, "finalUrl": final_url}
            
    except Exception:
        # Fallback to Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent=headers["User-Agent"])
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2500) # JS 프레임워크가 DOM을 조작할 시간 부여
            
            html = await page.content()
            final_url = page.url
            await browser.close()
            
            return {"html": html, "finalUrl": final_url}

async def scrape_product_metadata(url: str) -> dict:
    print(f"[{url}] 메타데이터 추출 파이프라인 시작...")
    
    final_url = url
    # 파이프라인 중간에 터져도 HTML을 살려서 폴백으로 넘기기 위해 최상단에 선언
    html = "" 
    title, brand, price, currency, availability, description, normalized_image_url = "", "", "", "", "", "", ""

    try:
        page_data = await _load_product_page(url)
        html = page_data["html"]
        final_url = page_data["finalUrl"]
        
        soup = BeautifulSoup(html, 'html.parser')
        
        products = _extract_json_ld_products(soup)
        product = products[0] if products else {}

        offers = product.get("offers", {})
        if isinstance(offers, list): offers = offers[0] if offers else {}

        images = product.get("image", [])
        if isinstance(images, str): images = [images]

        if isinstance(offers, dict) and offers:
            price = _clean_text(str(offers.get("price") or ""))
            currency = _clean_text(str(offers.get("priceCurrency") or ""))
            avail_raw = _clean_text(str(offers.get("availability") or ""))
            availability = avail_raw.split("/")[-1] if avail_raw else ""

        title_text = ""
        title_tag = soup.find("title")
        if title_tag: title_text = title_tag.get_text(strip=True)
            
        title = (_clean_text(product.get("name") or "") or 
                _extract_meta_content(soup, "og:title") or 
                title_text)
        
        image_url = (_clean_text(images[0] if images else "") or 
                    _extract_meta_content(soup, "og:image") or 
                    _extract_meta_content(soup, "twitter:image") or
                    _extract_meta_content(soup, "image"))

        if not image_url:
            common_selectors = [
                "img[id*='product']", "img[class*='product']", 
                "img[id*='main']", "img[class*='main']",
                "img[id*='goods']", "img[class*='goods']",
                ".product-image img", "#product-image img"
            ]
            for selector in common_selectors:
                img_tag = soup.select_one(selector)
                if img_tag and img_tag.get("src"):
                    image_url = img_tag["src"]
                    break

        description = (_clean_text(product.get("description") or "") or 
                    _extract_meta_content(soup, "og:description") or 
                    _extract_meta_content(soup, "description"))
        
        if product.get("brand"):
            if isinstance(product["brand"], dict):
                brand = _clean_text(product["brand"].get("name") or "")
            else:
                brand = _clean_text(str(product["brand"]))

        if not price:
            price = _extract_meta_content(soup, "product:price:amount") or _extract_meta_content(soup, "og:price:amount")
        if not currency:
            currency = _extract_meta_content(soup, "product:price:currency") or _extract_meta_content(soup, "og:price:currency")

        normalized_image_url = urljoin(final_url, image_url) if image_url else ""

        # --- 1차 방어막: 파싱이 실패하면(제목이나 이미지가 없으면) Gemini 폴백 ---
        if not title or not normalized_image_url:
            print(f"[{url}] 핵심 정보 누락. Gemini HTML 파싱 폴백 실행...")
            # 네트워크 중복 요청을 막기 위해 html을 같이 던져줌
            gemini_result = await fallback_with_gemini(url, html) 
            if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                return gemini_result

        return {
            "url": final_url,
            "title": title,
            "brand": brand,
            "price": price,
            "currency": currency,
            "availability": availability,
            "image_url": normalized_image_url,
            "description": description,
            "source": "json-ld/meta-tags",
        }

    except Exception as e:
        # --- 2차 방어막: 크롤링 자체가 에러나면 Gemini 폴백 ---
        print(f"[{url}] 파이프라인 에러 발생({e}). Gemini 폴백 실행...")
        if html and len(html.strip()) > 100:
            print(f"[{url}] 확보된 HTML로 Gemini 폴백 실행...")
            gemini_result = await fallback_with_gemini(url, html)
            if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                return gemini_result
        else:
            print(f"[{url}] 파싱할 HTML 소스가 없어 Gemini 폴백을 스킵합니다.")

        return {
            "url": url,
            "title": "추출 실패",
            "brand": "",
            "price": "",
            "currency": "",
            "availability": "",
            "image_url": "",
            "description": "데이터를 불러올 수 없습니다.",
            "source": "error-fallback",
        }