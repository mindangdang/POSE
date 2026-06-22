import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import curl_cffi.requests as requests
import json
from curl_cffi.requests.errors import RequestsError
import time
import random
import asyncio
import nodriver as uc
import os
from project.backend.app.manage.settings import load_backend_env
import tldextract
from project.backend.basic_functions.utils import _extract_text_vector_sync
import numpy as np
from deep_translator import GoogleTranslator

load_backend_env()
CATEGORY_LIST = ['outer', 'top', 'bottom', 'shoes', 'accessories', 'jewelry']
_CATEGORY_VECTORS = {cat: None for cat in CATEGORY_LIST}

def _clone_product_info():
    return {
        "title": None,
        "price": None,
        "brand": None,
        "image_url": None,
        "category": None,
        "is_available": False,
        "shop": None,
    }

def _normalize_price(price_value):
    if price_value is None:
        return None
    if isinstance(price_value, (int, float)):
        if isinstance(price_value, float) and price_value.is_integer():
            return int(price_value)
        return price_value
    if isinstance(price_value, str):
        text = price_value.strip()
        if not text:
            return None
        numeric = re.sub(r"[^\d]", "", text)
        return int(numeric) if numeric else text
    return str(price_value)

def _normalize_availability(availability_value):
    if availability_value is None:
        return False
    text = str(availability_value).strip().lower()
    if not text:
        return False
    if "판매중" in text or "in stock" in text or "available" in text:
        return True
    if "품절" in text or "outofstock" in text or "out of stock" in text or "sold out" in text or "soldout" in text:
        return False
    return True

def get_source_site_name(url: str) -> str | None:
    try:
        extracted = tldextract.extract(url)
        return extracted.domain or None
    except Exception:
        return None

async def get_clean_category(title: str, category: str) -> str:
    global _CATEGORY_VECTORS
    
    def cosine_similarity(vec1, vec2):
        if vec1 is None or vec2 is None:
            return 0.0
        vec1 = np.array(vec1).flatten()
        vec2 = np.array(vec2).flatten()
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    try:
        translated_title = GoogleTranslator(source='auto', target='en').translate(title)
        translated_category = GoogleTranslator(source='auto', target='en').translate(category) if category else ""
    except Exception as e:
        print(f"Translation failed, using original text: {e}")
        translated_title = title
        translated_category = category

    combined_text = f"{translated_title} {translated_category}".strip().lower()
    
    raw_query_vec = await _extract_text_vector_sync(combined_text)
    if raw_query_vec is None:
        print("[경고] 검색 텍스트의 벡터를 추출하지 못했습니다. 기본값 'unknown'을 반환합니다.")
        return "unknown"
        
    query_vec = np.array(raw_query_vec)
    best_category = None
    best_score = -1

    for category_name in CATEGORY_LIST:
        if _CATEGORY_VECTORS[category_name] is None:
            raw_cat_vec = await _extract_text_vector_sync(category_name)
            if raw_cat_vec is not None:
                _CATEGORY_VECTORS[category_name] = np.array(raw_cat_vec)
            else:
                print(f"[경고] 카테고리 '{category_name}'의 벡터 추출 실패. 건너뜁니다.")
                continue
        
        vec = _CATEGORY_VECTORS[category_name]
        if vec is None:
            continue

        score = cosine_similarity(query_vec, vec)

        if score > best_score:
            best_score = score
            best_category = category_name

    return best_category if best_category else "unknown"

def merge_product_info(*results):
    merged = {}
    for result in results:
        if not result:
            continue
        for key, value in result.items():
            if key not in merged:
                merged[key] = value
                continue
            if merged[key] in (None, "", [], {}):
                if value not in (None, "", [], {}):
                    merged[key] = value
    return merged
    
############################################# html crawling function ##################################################

def get_html_from_url(url: str, proxy=None):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    origin = f"{parsed_url.scheme}://{domain}"
    target_chrome = "chrome124"

    custom_headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "referer": f"{origin}/",
        "sec-ch-ua": '"Google Chrome";v="124", "Not:A-Brand";v="8", "Chromium";v="124"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        with requests.Session(impersonate=target_chrome, proxies=proxies) as session:
            try:
                pre_headers = custom_headers.copy()
                pre_headers["sec-fetch-site"] = "none"
                pre_headers.pop("referer", None)
                
                print(f"[정보] 1단계: 메인 홈 쿠키 굽기 시작 ({origin}/)")
                pre_response = session.get(f"{origin}/", headers=pre_headers, timeout=10)
                
                if pre_response.status_code >= 400:
                    print(f"[경고] 1단계 메인 홈 접속 실패 (상태 코드: {pre_response.status_code}). 우회를 중단합니다.")
                    return None
                    
            except RequestsError as e:
                print(f"[에러] 1단계 네트워크/WAF 차단 발생: {e}")
                return None
            
            time.sleep(random.uniform(1.5, 3.5))
            
            print(f"[정보] 2단계: 실제 타겟 페이지 요청 ({url})")
            response = session.get(url, headers=custom_headers, timeout=15)
            
            if response.status_code == 200:
                print(f"[성공] 최신 WAF 우회 및 HTML 수집 완료 ({url})")
                return response.text
            else:
                print(f"[실패] 최종 HTTP 상태 코드: {response.status_code}")
                if response.status_code in [403, 503]:
                    print("[힌트] 고도화된 행동 분석(Turnstile) 혹은 IP 평판 차단 가능성이 있습니다.")
                return None
                
    except RequestsError as e:
        print(f"[에러] curl_cffi 구동 중 치명적 오류: {e}")
        return None
    except Exception as e:
        print(f"[에러] 예기치 못한 시스템 오류: {e}")
        return None

async def get_html_from_browser(proxy_address: str, url: str):
    chrome_path = "/usr/bin/google-chrome"
    print("[정보] 코드스페이스 환경에서 크롬 가동 중...")
    
    config = uc.Config()
    config.browser_executable_path = chrome_path
    config.headless = True
    config.sandbox = False
    if proxy_address:
        config.browser_args.append(f"--proxy-server={proxy_address}")
    config.browser_args.append("--disable-dev-shm-usage")

    browser = None
    try:
        browser = await uc.start(config=config)
        print("[정보] 타겟 페이지 이동 중...")
        page = await browser.get(url)
        await page.evaluate("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        await asyncio.sleep(15)
        html = await page.get_content()
        print(f"[성공] HTML 수집 완료! (길이: {len(html)}자)")
        return html
        
    except Exception as e:
        print(f"[에러] nodriver 구동 중 오류 발생: {e}")
        return None
    finally:
        if browser:
            try:
                await browser.stop()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[경고] 브라우저 종료 중 예외 발생(무시 가능): {e}")
        
############################################# 🛠️ 대폭 수정한 html parsing function (soup 재사용) ##################################################

def parse_html_basic(soup):
    product_info = _clone_product_info()

    title_tag = soup.select_one("h1.Product-title")
    if title_tag:
        product_info["title"] = title_tag.get_text(strip=True)

    price_tag = soup.select_one("div.Product-price")
    if price_tag:
        product_info["price"] = _normalize_price(price_tag.get_text(strip=True))

    brand_tag = soup.select_one("h2.Product-brand")
    if brand_tag:
        product_info["brand"] = brand_tag.get_text(strip=True)

    image_tag = soup.select_one("img.Product-image")
    if image_tag:
        product_info["image_url"] = image_tag.get("src")

    buy_button = soup.select_one("div.Product-buy")
    if buy_button and "구매하기" in buy_button.get_text():
        product_info["is_available"] = True

    return product_info if product_info["title"] else None

def parse_html_with_json_ld(soup):
    product_info = _clone_product_info()
    json_ld_tags = soup.find_all("script", type="application/ld+json")

    for tag in json_ld_tags:
        try:
            if not tag.string:
                continue
            data = json.loads(tag.string)
            if isinstance(data, list):
                data = next((item for item in data if item.get("@type") == "Product"), data)

            if data.get("@type") != "Product":
                continue

            product_info["title"] = data.get("name") or data.get("headline")
            brand_data = data.get("brand")
            if isinstance(brand_data, dict):
                product_info["brand"] = brand_data.get("name")
            elif isinstance(brand_data, str):
                product_info["brand"] = brand_data

            images = data.get("image")
            if isinstance(images, list) and images:
                product_info["image_url"] = images[0]
            elif isinstance(images, str):
                product_info["image_url"] = images

            offers = data.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if offers:
                product_info["price"] = _normalize_price(offers.get("price"))
                product_info["is_available"] = _normalize_availability(offers.get("availability")) or _normalize_availability(offers.get("status"))

            product_info["category"] = data.get("category")
            break
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    return product_info if product_info["title"] else None

def parse_html_with_opengraph(soup):
    product_info = _clone_product_info()

    # 🛠️ 최적화: CSS 선택자를 사용해 단 한번의 스캔으로 og 태그와 description을 수집
    meta_tags = soup.select('meta[property^="og:"], meta[name="description"]')
    og_data = {}
    
    for tag in meta_tags:
        prop = tag.get("property")
        name = tag.get("name")
        content = tag.get("content")
        
        if not content:
            continue
            
        content_value = content.strip()
        if prop and prop.startswith("og:"):
            key = prop.replace("og:", "")
            og_data[key] = content_value
        elif name == "description" and "description" not in og_data:
            og_data["description"] = content_value

    if not og_data:
        return None

    product_info["title"] = og_data.get("title") or og_data.get("site_name")
    product_info["image_url"] = og_data.get("image")
    product_info["brand"] = og_data.get("brand")
    product_info["category"] = og_data.get("category")
    product_info["price"] = _normalize_price(
        og_data.get("product:price:amount")
        or og_data.get("price:amount")
        or og_data.get("og:price:amount")
    )
    product_info["is_available"] = _normalize_availability(
        og_data.get("availability") or og_data.get("product:availability") or og_data.get("status")
    )
    product_info["shop"] = og_data.get("site_name")

    if not product_info["title"]:
        return None

    print("[성공] OpenGraph 데이터 추출 완료")
    return product_info

def parse_musinsa_html(soup):
    script_tag = soup.find("script", id="pdp-data")
    if not script_tag or not script_tag.string:
        print("[오류] pdp-data 스크립트 태그를 찾을 수 없습니다.")
        return None

    try:
        match = re.search(
            r"window\.__MSS_FE__\.product\.state\s*=\s*(\{.*?\});",
            script_tag.string,
            re.DOTALL,
        )
        if not match:
            print("[오류] 스크립트 내에서 product.state JSON 데이터를 찾지 못했습니다.")
            return None

        json_data = json.loads(match.group(1))
        return {
            "title": json_data.get("goodsNm"),
            "brand": json_data.get("brandInfo", {}).get("brandName"),
            "category": json_data.get("baseCategoryFullPath"),
            "price": _normalize_price(json_data.get("goodsPrice", {}).get("salePrice") or json_data.get("goodsPrice", {}).get("normalPrice")),
            "image_url": json_data.get("thumbnailImageUrl"),
            "shop": "Musinsa",
            'is_available': not json_data.get("isOutOfStock"),
        }
    except Exception as e:
        print(f"[오류] 파싱 중 에러 발생: {e}")
        return None

########################################################################################################################

async def product_crawler(url):
    base_proxy_url = os.environ.get("BASE_PROXY_URL")
    max_retries = 15  
    retry_count = 0
    html_content = None
    shop_name = get_source_site_name(url)

    while html_content is None and retry_count < max_retries:
        retry_count += 1
        chosen_proxy = base_proxy_url
        print(f"[시도 {retry_count}/{max_retries}] 선택된 프록시: {chosen_proxy}")
        html_content = get_html_from_url(url, proxy=chosen_proxy)

        if html_content is None:
            print(f"[실패] curl_cffi로 HTML을 가져오는데 실패했습니다. nodriver로 재시도합니다.")
            html_content = await get_html_from_browser(chosen_proxy, url)

    final_result = None
    if html_content is not None:
        print(f"[성공] 최종 HTML 확보 완료. 파싱을 시작합니다.")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        if "musinsa.com" in url:
            final_result = parse_musinsa_html(soup)
        else:
            result_basic = parse_html_basic(soup)
            result_json_ld = parse_html_with_json_ld(soup)
            result_opengraph = parse_html_with_opengraph(soup)

            final_result = merge_product_info(
                result_basic,
                result_json_ld,
                result_opengraph,
            )
        
        if final_result is not None:
            print(f"[성공] HTML 파싱 완료")
            final_result['shop'] = shop_name
            clean_category = await get_clean_category(final_result.get('title') or '', final_result.get('category') or '')
            title_val = final_result.get('title')
            category_val = final_result.get('category')
            if title_val and category_val:
                clean_category = await get_clean_category(title_val, category_val)
                final_result['category'] = clean_category
            return final_result
    else:
        print("[최종 실패] 모든 재시도가 실패했으며 HTML을 가져오지 못했습니다.")
        return None


if __name__ == "__main__":
    url_dict = {'musinsa' : "https://www.musinsa.com/products/3513309", 
                'fetching' : 'https://fetching.co.kr/product/58383691/%EC%8A%A4%EB%8B%88%EC%BB%A4%EC%A6%88%20V-S1%20%EC%BB%A8%ED%83%9D%ED%8A%B8%20%EB%B8%94%EB%9E%99', 
                'fruitsfamily' : 'https://fruitsfamily.com/product/5qjtk/12fw-%EB%B0%B1%EC%8A%A4%ED%8B%B0%EC%B9%98-%EB%B8%8C%EC%9D%B4%EB%84%A5-%EB%8B%88%ED%8A%B8',
                'jaded' : 'https://jadedldn.com/en-kr/products/product-of-age-cinch-back-xl-colossus',
                'zara' : '',
                "WORKSOUT":'',
                "8DIVISION":'',
                "IAMSHOP":'',
                "THE BOUNCE":'',
                "THE X SHOP":'',
                "COLLECTIV":'',
                "KREAM":'',
                "EQL":'https://www.eqlstore.com/product/GPFN26060473023/detail?_gl=1*1cp9enf*_gcl_aw*R0NMLjE3ODE5NjY4OTYuRUFJYUlRb2JDaE1JcHNMOTlvZVdsUU1WTngxN0J4MWtOeExSRUFBWUFTQUFFZ0pMZ1BEX0J3RQ..*_gcl_au*MTI5Nzg1MTI4OS4xNzgxOTY2ODk2*_ga*MjEzOTc5MjkzMC4xNzgxOTY2ODk2*_ga_E7EBD0FG29*czE3ODE5NjY4OTUkbzEkZzAkdDE3ODE5NjY4OTUkajYwJGwwJGgw',
                "29CM":'https://www.29cm.co.kr/products/4012083', # url정규화 필요
                "Bunjang":'',
                }
    url = url_dict['musinsa']
    result = asyncio.run(product_crawler(url))
    print(result) # python -m project.backend.basic_functions.crawlers.product_crawler