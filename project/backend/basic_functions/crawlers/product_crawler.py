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
    soup = BeautifulSoup(html_content, 'html.parser')
    
    product_info = {
        "title": None,
        "price": None,
        "brand": None,
        "image": None,
        "is_available": False
    }
    
    # 1. 상품명 추출 (h1.Product-title)
    title_tag = soup.select_one("h1.Product-title")
    if title_tag:
        product_info["title"] = title_tag.get_text(strip=True)
        
    # 2. 가격 추출 (div.Product-price에서 숫자만 추출)
    price_tag = soup.select_one("div.Product-price")
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        # '120,000원'에서 숫자만 남기기
        price_numeric = re.sub(r'[^\d]', '', price_text)
        product_info["price"] = int(price_numeric) if price_numeric else None

    # 3. 브랜드 추출 (h2.Product-brand 내부의 a 태그)
    brand_tag = soup.select_one("h2.Product-brand a")
    if brand_tag:
        product_info["brand"] = brand_tag.get_text(strip=True)

    # 4. 이미지 추출 (img.Product-image의 src 속성)
    image_tag = soup.select_one("img.Product-image")
    if image_tag:
        product_info["image"] = image_tag.get("src")

    # 5. 판매중 여부 판단
    # '구매하기' 버튼이 존재하고, '품절' 관련 클래스나 텍스트가 없는지 확인
    buy_button = soup.select_one("div.Product-buy")
    if buy_button and "구매하기" in buy_button.get_text():
        # 하단 추천 상품 목록에 있는 'ProductPreview-sold'(품절 표시)와 헷갈리지 않도록 
        # 메인 구매 버튼의 텍스트와 상태로 판별합니다.
        product_info["is_available"] = True
    
    if not product_info["title"]:
        return None

    return product_info

def parse_html_with_json_ld(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    product_info = {
        "title": None,
        "price": None,
        "brand": None,
        "image": None,
        "is_available": False
    }
    
    # 1. HTML 내의 모든 JSON-LD 태그 검색
    json_ld_tags = soup.find_all("script", type="application/ld+json")
    
    for tag in json_ld_tags:
        try:
            # 문자열을 파이썬 딕셔너리로 변환
            data = json.loads(tag.string)
            
            # 여러 개의 JSON-LD 중 '@type'이 'Product'인 것만 타겟팅
            if data.get("@type") == "Product":
                
                # 1) 상품명 추출
                product_info["title"] = data.get("name")
                
                # 2) 브랜드 추출 (문자열일 수도 있고, 딕셔너리 구조일 수도 있음)
                brand_data = data.get("brand")
                if isinstance(brand_data, dict):
                    product_info["brand"] = brand_data.get("name")
                elif isinstance(brand_data, str):
                    product_info["brand"] = brand_data
                
                # 3) 이미지 추출 (리스트 형태면 첫 번째 이미지 사용)
                images = data.get("image")
                if isinstance(images, list) and len(images) > 0:
                    product_info["image"] = images[0]
                elif isinstance(images, str):
                    product_info["image"] = images
                
                # 4) 가격 및 판매 여부 추출 (offers 구조 해석)
                offers = data.get("offers")
                if offers:
                    # 가격 추출
                    product_info["price"] = offers.get("price")
                    
                    # 판매중 여부 추출 (InStock 상태인지 확인)
                    availability = offers.get("availability", "")
                    if "InStock" in availability or "in stock" in availability.lower():
                        product_info["is_available"] = True
                        
                # 유효한 Product 데이터를 찾았으므로 루프 종료
                break
                
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            # JSON 파싱 에러 등이 나면 다음 태그로 넘어감
            continue

    if not product_info["title"]:
        return None

    return product_info

def parse_html_with_opengraph(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")
    
    # OpenGraph 메타 태그 검색
    # <meta property="og:..." content="..."> 구조를 타겟팅합니다.
    meta_tags = soup.find_all("meta", property=lambda x: x and x.startswith("og:"))
    
    # 데이터를 담을 딕셔너리 초기화
    og_data = {}
    
    # 발견된 og 태그들을 순회하며 key-value 형태로 저장
    for tag in meta_tags:
        property_name = tag.get("property")
        content_value = tag.get("content")
        
        if property_name and content_value:
            # "og:" 접두사를 제외한 키값만 저장 (예: og:title -> title)
            key = property_name.replace("og:", "")
            og_data[key] = content_value.strip()
            
    # 트위터 카드나 일반 description 등 유용한 메타 정보가 있다면 보완용으로 추가 추출
    if "description" not in og_data:
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag:
            og_data["description"] = desc_tag.get("content", "").strip()

    if not og_data:
        print("[경고] HTML 내에서 OpenGraph 메타 태그를 찾지 못했습니다.")
        return None
        
    print("[성공] OpenGraph 데이터 추출 완료")
    return og_data

############################################# custom parsing fuction ##################################################

def parse_musinsa_html(html_content):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. pdp-data 라는 ID를 가진 스크립트 태그를 조준합니다.
    script_tag = soup.find("script", id="pdp-data")

    if not script_tag:
        print("[오류] pdp-data 스크립트 태그를 찾을 수 없습니다.")
        return None

    script_text = script_tag.string

    try:
        # 2. 정규표현식으로 window.__MSS_FE__.product.state = { ... }; 부분을 추출합니다.
        # state = 뒤에 오는 JSON 객체({ ... })만 완벽하게 매칭합니다.
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

        # 3. 추출한 문자열을 파이썬 딕셔너리로 변환합니다.
        json_data = json.loads(match.group(1))

        # 4. 안전하게 원하는 데이터만 쏙쏙 골라냅니다.
        product_info = {
            "상품번호": json_data.get("goodsNo"),
            "상품명(국문)": json_data.get("goodsNm"),
            "상품명(영문)": json_data.get("goodsNmEng"),
            "브랜드": json_data.get("brandInfo", {}).get("brandName"),
            "카테고리": json_data.get("baseCategoryFullPath"),
            "정가": json_data.get("goodsPrice", {}).get("normalPrice"),
            "할인가": json_data.get("goodsPrice", {}).get("salePrice"),
            "할인율": json_data.get("goodsPrice", {}).get("discountRate"),
            "메인이미지": json_data.get("thumbnailImageUrl"),
            "리뷰수": json_data.get("goodsReview", {}).get("totalCount"),
            "평점": json_data.get("goodsReview", {}).get("satisfactionScore"),
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
    proxify_url = "http://pubproxy.com/api/proxy?country=KR&type=http&anon=elite"
    proxy_list = []
    
    try:
        response = requests.get(proxify_url, timeout=5) 
        if response.status_code == 200:
            proxy_list = response.text.strip().split("\n")
            print(f"[정보] 총 {len(proxy_list)}개의 무료 프록시를 가져왔습니다.")
    except Exception as e:
        print(f"[경고] 프록시 리스트를 가져오는데 실패했습니다: {e}")

    max_retries = 15  
    retry_count = 0
    html_content = None
    
    while html_content is None and retry_count < max_retries:
        retry_count += 1
        
        if proxy_list:
            chosen_proxy = random.choice(proxy_list)
            print(f"[시도 {retry_count}/{max_retries}] 선택된 프록시: {chosen_proxy}")
        else:
            chosen_proxy = None
            print(f"[시도 {retry_count}/{max_retries}] 사용할 수 있는 프록시 리스트가 없어 프록시 없이 시도합니다.")

        html_content = get_html_from_url(url, proxy=chosen_proxy)
        if html_content is None:
            print(f"[실패] curl_cffi로 HTML을 가져오는데 실패했습니다. nodriver로 재시도합니다.")
            html_content = await get_html_from_browser(chosen_proxy, url)
        
        if html_content is None:
            print(f"[실패] 해당 프록시({chosen_proxy})가 죽었거나 차단되었습니다. 다른 프록시로 재시도합니다.")
            if chosen_proxy in proxy_list:
                proxy_list.remove(chosen_proxy)

    result = None
    if html_content is not None:
        print(f"[성공] 최종 HTML 확보 완료. 파싱을 시작합니다. {html_content}")
        
        result = parse_html_basic(html_content)
        if result is None:
            result = parse_html_with_json_ld(html_content)
            if result is None:
                result = parse_html_with_opengraph(html_content)
        
        if result is not None:
            print(f"[성공] HTML 파싱 완료")
            return result
    else:
        print("[최종 실패] 모든 재시도가 실패했으며 HTML을 가져오지 못했습니다.")
        return None


if __name__ == "__main__":

    url_dict = {'musinsa' : "https://www.musinsa.com/products/3513309", 
                'fetching' : 'https://fetching.co.kr/product/58383691/%EC%8A%A4%EB%8B%88%EC%BB%A4%EC%A6%88%20V-S1%20%EC%BB%A8%ED%83%9D%ED%8A%B8%20%EB%B8%94%EB%9E%99', 
                'fruitsfamily' : 'https://fruitsfamily.com/product/5qjtk/12fw-%EB%B0%B1%EC%8A%A4%ED%8B%B0%EC%B9%98-%EB%B8%8C%EC%9D%B4%EB%84%A5-%EB%8B%88%ED%8A%B8',
                'jaded' : 'https://jadedldn.com/en-kr/products/product-of-age-cinch-back-xl-colossus'
                }
    url = url_dict['jaded']
    result = asyncio.run(product_crawler(url))
    print(result)
  





