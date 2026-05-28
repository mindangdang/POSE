/**
 * 텍스트 정규화 (공백 제거 및 줄바꿈 정리)
 */
function cleanText(v) {
  if (!v) return "";
  return String(v).replace(/\s+/g, " ").trim();
}

/**
 * 가격 정규화 (숫자만 추출)
 */
function normalizePrice(p) {
  if (!p) return "";
  return String(p).replace(/[^0-9]/g, "");
}

/**
 * 절대 경로 URL 생성 (트래킹 파라미터 제거)
 */
function getCanonicalUrl() {
  const canonical = document.querySelector('link[rel="canonical"]')?.href;
  if (canonical) return canonical.split('?')[0];
  return window.location.origin + window.location.pathname;
}

/**
 * 메타 태그 추출 (og, twitter, itemprop 우선순위)
 */
function getMeta(property) {
  const el =
    document.querySelector(`meta[property="${property}"]`) ||
    document.querySelector(`meta[name="${property}"]`) ||
    document.querySelector(`meta[itemprop="${property}"]`);
  return el?.content || "";
}

/**
 * 이미지 정규화: Lazy loading 및 srcset 대응
 */
function getBestImage(imgEl, metaImg) {
  if (!imgEl) return metaImg || "";
  
  const src = imgEl.getAttribute('data-src') || 
              imgEl.getAttribute('data-original') || 
              imgEl.getAttribute('data-lazy-src') ||
              imgEl.getAttribute('data-image') ||
              imgEl.src;
              
  if (src && !src.includes('base64') && !src.includes('placeholder')) {
    try {
      return new URL(src, window.location.href).href;
    } catch (e) {
      return metaImg;
    }
  }
  return metaImg || src || "";
}

/**
 * 우선순위가 높은 사이트 선택자 (자주 사용되는 쇼핑몰 우선)
 */
const SITE_SELECTORS = {
  "musinsa.com": {
    title: "h1.product_title em, .product-detail__sc-190p9as-0, .product_name",
    price: ".price_detail .real em, .product-detail__sc-1631h6w-1, #goods_price",
    brand: ".product_title span, .product_detail__sc-190p9as-2, .product-brand",
    image: "#bigimg, .product-image img, [role='img'] img"
  },
  "ably.co.kr": {
    title: ".goods-name, h1",
    price: ".price-real, .price-final",
    brand: ".store-name, .brand-name",
    image: ".image-container img, [data-role='main-img'] img"
  },
  "29cm.co.kr": {
    title: "h1, h2.css-1698zsd",
    price: ".price-current, .css-1atv97s",
    brand: ".brand-info, .css-517860",
    image: ".product-image-main img, .css-8atq4r img"
  },
  "stylesha.com": {
    title: "h1.tit, .product-title",
    price: ".price em, .price-content",
    brand: ".brand-link, .brand-name",
    image: ".prod-image-main img, .image-main"
  }
};

/**
 * JSON-LD 재귀 탐색: 깊은 구조에서 Product 타입 찾기
 */
function findProductInObject(obj) {
  if (!obj || typeof obj !== 'object') return null;
  if (obj['@type'] === 'Product') return obj;
  
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const found = findProductInObject(item);
      if (found) return found;
    }
  } else {
    for (const key in obj) {
      const found = findProductInObject(obj[key]);
      if (found) return found;
    }
  }
  return null;
}

function extractJSONLD() {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of scripts) {
    try {
      const data = JSON.parse(script.textContent);
      const found = findProductInObject(data);
      if (found) return found;
    } catch (e) {
      // JSON parsing 오류 무시
    }
  }
  return null;
}

/**
 * 메인 추출 로직 (JSON-LD -> Meta -> Selector 우선순위)
 */
function extractProduct() {
  const jsonld = extractJSONLD();
  const hostname = window.location.hostname;
  const selectors = Object.entries(SITE_SELECTORS).find(([domain]) => hostname.includes(domain))?.[1];

  // 1. 제목 추출 (JSON-LD -> Meta -> Selector -> page title)
  let title = jsonld?.name || getMeta("og:title");
  if (!title && selectors?.title) {
    const el = document.querySelector(selectors.title);
    if (el) title = el.innerText;
  }
  if (!title) title = document.title || "";

  // 2. 이미지 처리 (Meta -> Selector -> JSON-LD)
  let image = getMeta("og:image");
  if (!image && selectors?.image) {
    const el = document.querySelector(selectors.image);
    if (el) image = getBestImage(el, "");
  }
  if (!image) {
    image = jsonld?.image;
    if (Array.isArray(image)) image = image[0] || "";
  }
  
  // 3. 가격 처리 (Meta -> Selector -> JSON-LD)
  let price = getMeta("product:price:amount") || getMeta("og:price:amount");
  if (!price && selectors?.price) {
    const el = document.querySelector(selectors.price);
    if (el) price = el.innerText;
  }
  if (!price) price = jsonld?.offers?.price || "";

  // 4. 브랜드 (JSON-LD -> Meta -> Selector)
  let brand = "";
  if (jsonld?.brand) {
    brand = typeof jsonld.brand === 'object' ? jsonld.brand.name : jsonld.brand;
  }
  if (!brand) brand = getMeta("product:brand");
  if (!brand && selectors?.brand) {
    const el = document.querySelector(selectors.brand);
    if (el) brand = el.innerText;
  }

  return {
    url: getCanonicalUrl(),
    title: cleanText(title),
    image_url: String(image).trim(),
    description: cleanText(jsonld?.description || getMeta("og:description")),
    brand: cleanText(brand),
    price: normalizePrice(price) || null,
    currency: jsonld?.offers?.priceCurrency || getMeta("product:price:currency") || "KRW",
    source: "extension_content_script"
  };
}

/**
 * SPA/CSR 대응: 최대 6초간 재시도하며 데이터 확인
 */
async function extractWithRetry(sendResponse) {
  let attempts = 0;
  const maxAttempts = 10; // 6초 (10 * 600ms)
  
  const check = () => {
    const data = extractProduct();
    const hasRequiredData = 
      data.title && 
      String(data.title).trim().length > 0 && 
      data.image_url && 
      String(data.image_url).trim().length > 0 && 
      (data.price || data.brand);
    
    if (hasRequiredData || attempts >= maxAttempts) {
      if (!hasRequiredData) {
        console.warn("필수 데이터 미충족:", data);
      }
      sendResponse(data);
    } else {
      attempts++;
      setTimeout(check, 600);
    }
  };
  check();
}

/**
 * 메시지 리스너: content script 실행
 */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "EXTRACT_PRODUCT") {
    extractWithRetry(sendResponse);
    return true; // 비동기 응답 활성화
  }
});