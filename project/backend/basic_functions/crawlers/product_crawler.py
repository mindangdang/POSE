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

load_backend_env()

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

def get_clean_category(title: str, category: str) -> str:
    category_vec_lst = []
    def cosine_similarity(vec1, vec2):
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    title_vec = _extract_text_vector_sync(title)
    category_vec = _extract_text_vector_sync(category)

    # title + category 정보를 모두 반영
    query_vec = (
        np.array(title_vec) + np.array(category_vec)
    ) / 2

    best_category = None
    best_score = -1

    for category_name, vec in category_vec_lst:
        score = cosine_similarity(query_vec, vec)

        if score > best_score:
            best_score = score
            best_category = category_name

    return best_category

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
    proxy = proxy

    # 1.Chrome의 실제 헤더 순서와 구조 모사
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
        # 2. curl_cffi 세션 생성 (HTTP/2 및 Chrome TLS 핑거프린트 완전 모사)
        # impersonate='chrome' 옵션이 JA3/JA4 핑거프린트와 HTTP/2 세팅을 완전히 실제 크롬처럼 만듬.
        with requests.Session(impersonate=target_chrome, proxies=proxies) as session:
            
            # [1단계] 메인 홈 호출 및 검증 (쿠키 획득 및 챌린지 우회)
            try:
                pre_headers = custom_headers.copy()
                pre_headers["sec-fetch-site"] = "none"
                pre_headers.pop("referer", None)
                
                print(f"[정보] 1단계: 메인 홈 쿠키 굽기 시작 ({origin}/)")
                pre_response = session.get(f"{origin}/", headers=pre_headers, timeout=10)
                
                # 1단계 실패 조건 검증 (403, 503 등으로 막혔다면 2단계를 진행할 이유가 없음)
                if pre_response.status_code >= 400:
                    print(f"[경고] 1단계 메인 홈 접속 실패 (상태 코드: {pre_response.status_code}). 우회를 중단합니다.")
                    return None
                    
            except RequestsError as e:
                print(f"[에러] 1단계 네트워크/WAF 차단 발생: {e}")
                return None
            
            # [행동 패턴 제어] 사람의 행동과 유사하게 타임아웃 지연 (지연 시간 다각화)
            # 고정된 패턴을 피하기 위해 조금 더 유연한 대기 시간을 가집니다.
            time.sleep(random.uniform(1.5, 3.5))
            
            # [2단계] 획득한 쿠키 권한을 가지고 실제 상세 페이지 요청
            print(f"[정보] 2단계: 실제 타겟 페이지 요청 ({url})")
            response = session.get(url, headers=custom_headers, timeout=15)
            
            # 상태 코드 확인
            if response.status_code == 200:
                print(f"[성공] 최신 WAF 우회 및 HTML 수집 완료 ({url})")
                return response.text
            else:
                print(f"[실패] 최종 HTTP 상태 코드: {response.status_code}")
                # Cloudflare Turnstile 등에 걸렸을 때의 상태 코드 대응 (403, 503)
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
        #traceback.print_exc()
        return None

    finally:
        if browser:
            try:
                await browser.stop()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[경고] 브라우저 종료 중 예외 발생(무시 가능): {e}")
        
############################################# html parsing function ##################################################
def parse_html_basic(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    product_info = _clone_product_info()

    title_tag = soup.select_one("h1.Product-title")
    if title_tag:
        product_info["title"] = title_tag.get_text(strip=True)

    price_tag = soup.select_one("div.Product-price")
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        product_info["price"] = _normalize_price(price_text)

    brand_tag = soup.select_one("h2.Product-brand")
    if brand_tag:
        product_info["brand"] = brand_tag.get_text(strip=True)

    image_tag = soup.select_one("img.Product-image")
    if image_tag:
        product_info["image_url"] = image_tag.get("src")

    buy_button = soup.select_one("div.Product-buy")
    if buy_button and "구매하기" in buy_button.get_text():
        product_info["is_available"] = True

    if not product_info["title"]:
        return None

    return product_info

def parse_html_with_json_ld(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    product_info = _clone_product_info()
    json_ld_tags = soup.find_all("script", type="application/ld+json")

    for tag in json_ld_tags:
        try:
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
            product_info["shop"] = None
            break

        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    if not product_info["title"]:
        return None

    return product_info

def parse_html_with_opengraph(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")
    product_info = _clone_product_info()

    meta_tags = soup.find_all("meta", property=lambda x: x and x.startswith("og:"))
    og_data = {}
    for tag in meta_tags:
        property_name = tag.get("property")
        content_value = tag.get("content")
        if property_name and content_value:
            key = property_name.replace("og:", "")
            og_data[key] = content_value.strip()

    if "description" not in og_data:
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag:
            og_data["description"] = desc_tag.get("content", "").strip()

    if not og_data:
        print("[경고] HTML 내에서 OpenGraph 메타 태그를 찾지 못했습니다.")
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


############################################# custom parsing fuction ##################################################

def parse_musinsa_html(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")
    script_tag = soup.find("script", id="pdp-data")

    if not script_tag:
        print("[오류] pdp-data 스크립트 태그를 찾을 수 없습니다.")
        return None

    script_text = script_tag.string

    try:
        match = re.search(
            r"window\.__MSS_FE__\.product\.state\s*=\s*(\{.*?\});",
            script_text,
            re.DOTALL,
        )

        if not match:
            print(
                "[오류] 스크립트 내에서 product.state JSON 데이터를 찾지 못했습니다."
            )
            return None

        json_data = json.loads(match.group(1))

        product_info = {
            "title": json_data.get("goodsNm"),
            "brand": json_data.get("brandInfo", {}).get("brandName"),
            "category": json_data.get("baseCategoryFullPath"),
            "original_price": json_data.get("goodsPrice", {}).get("normalPrice"),
            "discounted_price": json_data.get("goodsPrice", {}).get("salePrice"),
            "image_url": json_data.get("thumbnailImageUrl"),
            "shop": "Musinsa",
            'is_available': not json_data.get("isOutOfStock"),
            #"review_count": json_data.get("goodsReview", {}).get("totalCount"),
            #"rating": json_data.get("goodsReview", {}).get("satisfactionScore"),
            #"discount_rate": json_data.get("goodsPrice", {}).get("discountRate"),
        }

        return product_info

    except json.JSONDecodeError as je:
        print(f"[오류] JSON 파싱 실패: {je}")
        return None
    except Exception as e:
        print(f"[오류] 파싱 중 예상치 못한 에러 발생: {e}")
        return None

########################################################################################################################

async def product_crawler(url):
    base_proxy_url = os.environ.get("BASE_PROXY_URL")
    '''
    proxify_url = "http://pubproxy.com/api/proxy?country=KR&type=http&anon=elite"
    proxy_list = []
    
    try:
        response = requests.get(proxify_url, timeout=5) 
        if response.status_code == 200:
            proxy_list = response.text.strip().split("\n")
            print(f"[정보] 총 {len(proxy_list)}개의 무료 프록시를 가져왔습니다.")
    except Exception as e:
        print(f"[경고] 프록시 리스트를 가져오는데 실패했습니다: {e}")
    '''
    max_retries = 15  
    retry_count = 0
    html_content = None
    shop_name = get_source_site_name(url)

    while html_content is None and retry_count < max_retries:
        retry_count += 1
        
        '''
        if proxy_list:
            chosen_proxy = random.choice(proxy_list)
            print(f"[시도 {retry_count}/{max_retries}] 선택된 프록시: {chosen_proxy}")
        else:
            chosen_proxy = None
            print(f"[시도 {retry_count}/{max_retries}] 사용할 수 있는 프록시 리스트가 없어 프록시 없이 시도합니다.")
        '''
        chosen_proxy = base_proxy_url
        print(f"[시도 {retry_count}/{max_retries}] 선택된 프록시: {chosen_proxy}")
        html_content = get_html_from_url(url, proxy=chosen_proxy)

        if html_content is None:
            print(f"[실패] curl_cffi로 HTML을 가져오는데 실패했습니다. nodriver로 재시도합니다.")
            html_content = await get_html_from_browser(chosen_proxy, url)
        
        if html_content is None:
            print(f"[실패] 해당 프록시({chosen_proxy})가 죽었거나 차단되었습니다. 다른 프록시로 재시도합니다.")
            #if chosen_proxy in proxy_list:
                #proxy_list.remove(chosen_proxy)

    final_result = None
    if html_content is not None:
        print(f"[성공] 최종 HTML 확보 완료. 파싱을 시작합니다. {html_content}")
        if "musinsa.com" in url:
            final_result = parse_musinsa_html(html_content)
        else:
            result_basic = parse_html_basic(html_content)
            result_json_ld = parse_html_with_json_ld(html_content)
            result_opengraph = parse_html_with_opengraph(html_content)

            final_result = merge_product_info(
                result_basic,
                result_json_ld,
                result_opengraph,
            )
        
        if final_result is not None:
            print(f"[성공] HTML 파싱 완료")
            final_result['shop'] = shop_name
            #clean_category = get_clean_category(result['title'], result['category'])
            #result['category'] = clean_category
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
                "EQL":'',
                "29CM":'',
                "Bunjang":'',
                }
    url = url_dict['zara']
    result = asyncio.run(product_crawler(url))
    print(result)
  

# python -m project.backend.basic_functions.crawlers.product_crawler