import os
import re
import json
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydantic import BaseModel, Field
from typing import Optional

from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ---안전한 데이터 파싱을 위한 Pydantic 스키마 ---
class ProductFallbackSchema(BaseModel):
    title: str
    price: str
    currency: str
    image_url: str
    brand: Optional[str] = ""
    description: Optional[str] = ""

async def fallback_with_gemini(url: str):
    try:
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        prompt = f"""Extract accurate product information from this URL: {url}. 
      CRITICAL INSTRUCTIONS:
      1. IMAGE URL: You MUST find the ACTUAL, ORIGINAL image URL of the product from the page's source code or metadata. Look specifically for 'og:image', 'twitter:image', or the primary <img> tag associated with the product. 
      2. NO PLACEHOLDERS: Do NOT use placeholder services. 
      3. ABSOLUTE URLS: If the image URL found is relative, you MUST convert it to an absolute URL.
      4. ACCURACY: Ensure the product name, price, and brand match exactly what is shown on the page."""

        print(f"[{url}] Gemini 폴백 분석 시작...")
        
        # LLM 호출을 스레드 풀로 분리하여 서버 멈춤 방지
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductFallbackSchema, # Pydantic 스키마 강제
                temperature=0.1
            )
        )
        
        data = response.parsed
        real_image_url = data.image_url 
        
        try:
            print(f"[{url}] 원본 웹페이지에서 고화질 이미지 메타태그 직접 교차 검증 중...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            # 비동기 httpx 클라이언트 사용
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http_client:
                response_html = await http_client.get(url, headers=headers)
                
            soup = BeautifulSoup(response_html.text, 'html.parser')
            
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                real_image_url = og_img["content"]
            else:
                tw_img = soup.find("meta", attrs={"name": "twitter:image"})
                if tw_img and tw_img.get("content"):
                    real_image_url = tw_img["content"]
                    
            if real_image_url.startswith("/"):
                real_image_url = urljoin(url, real_image_url)
                
        except Exception as img_e:
            print(f"웹페이지 이미지 직접 추출 실패 (LLM 추출값 유지): {img_e}")
        
        return {
            "url": url,
            "title": data.title,
            "brand": data.brand,
            "price": data.price,
            "currency": data.currency,
            "image_url": real_image_url,
            "description": data.description,
            "source": "gemini-url-context-backend" 
        }
    except Exception as e:
        print(f"Gemini 폴백 추출 실패: {e}")
        return None

# -----------------------------------

def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r'\s+', ' ', str(value)).strip()

def _extract_json_ld_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    products = []
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            raw = script.string
            if not raw: continue
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

def _extract_meta_content(html: str, property_name: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    content = ""
    meta = soup.find('meta', attrs={'property': property_name})
    if meta and meta.get('content'): content = meta['content']
    if not content:
        meta = soup.find('meta', attrs={'name': property_name})
        if meta and meta.get('content'): content = meta['content']
    if not content:
        meta = soup.find('meta', attrs={'itemprop': property_name})
        if meta and meta.get('content'): content = meta['content']
    return _clean_text(content)

# JS 렌더링이 필요한 사이트를 방어하는 핵심 함수
async def _load_product_page(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
            final_url = str(response.url)

            # 무신사, 크림, 자라 등 SPA 사이트이거나 메타태그가 안 보이면 Playwright로 넘깁니다.
            is_js_heavy = any(domain in url for domain in ["musinsa.com", "kream.co.kr", "zara.com"])
            if is_js_heavy or "<script" not in html or ("og:title" not in html and "application/ld+json" not in html):
                print(f"[{url}] JS 렌더링이 필요한 사이트입니다. Playwright 엔진을 가동합니다.")
                raise ValueError("Need JS rendering")

            return {"html": html, "finalUrl": final_url}
            
    except Exception:
        # Fallback to Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent=headers["User-Agent"])
            page = await context.new_page()
            
            # 페이지가 완전히 그려질 때까지 기다립니다.
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000) 
            
            html = await page.content()
            final_url = page.url
            await browser.close()
            
            return {"html": html, "finalUrl": final_url}

# 끊어져 있던 _load_product_page를 메인 로직에 연결
async def scrape_product_metadata(url: str) -> dict:
    print(f"[{url}] 메타데이터 추출 파이프라인 시작...")
    
    final_url = url
    title, brand, price, currency, availability, description, normalized_image_url = "", "", "", "", "", "", ""

    try:
        # 1. 이제 _load_product_page를 호출하여 SPA 사이트를 방어합니다! 
        page_data = await _load_product_page(url)
        html = page_data["html"]
        final_url = page_data["finalUrl"]
        
        soup = BeautifulSoup(html, 'html.parser')
        products = _extract_json_ld_products(html)
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
                _extract_meta_content(html, "og:title") or 
                title_text)
        
        image_url = (_clean_text(images[0] if images else "") or 
                    _extract_meta_content(html, "og:image") or 
                    _extract_meta_content(html, "twitter:image") or
                    _extract_meta_content(html, "image"))

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
                    _extract_meta_content(html, "og:description") or 
                    _extract_meta_content(html, "description"))
        
        if product.get("brand"):
            if isinstance(product["brand"], dict):
                brand = _clean_text(product["brand"].get("name") or "")
            else:
                brand = _clean_text(str(product["brand"]))

        if not price:
            price = _extract_meta_content(html, "product:price:amount") or _extract_meta_content(html, "og:price:amount")
        if not currency:
            currency = _extract_meta_content(html, "product:price:currency") or _extract_meta_content(html, "og:price:currency")

        normalized_image_url = urljoin(final_url, image_url) if image_url else ""

        # --- 1차 방어막: 파싱이 실패하면(제목이나 이미지가 없으면) Gemini 폴백 (비동기 호출) ---
        if not title or not normalized_image_url:
            print(f"[{url}] 핵심 정보 누락. Gemini 폴백 실행...")
            gemini_result = await fallback_with_gemini(url) # await 추가!
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
        # --- 2차 방어막: 크롤링 자체가 에러나면 Gemini 폴백 (비동기 호출) ---
        print(f"[{url}] 파이프라인 에러 발생({e}). Gemini 폴백 실행...")
        gemini_result = await fallback_with_gemini(url) # await 추가!
        if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
            return gemini_result

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