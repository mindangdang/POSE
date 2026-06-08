import os
import re
import json
import uuid
import time
import random
import asyncio
import logging
from collections import defaultdict
from urllib.parse import urlunparse
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Type, List, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from pydantic import BaseModel,Field
import curl_cffi.requests as requests
from google import genai
from google.genai import types
from playwright.async_api import async_playwright, Browser
from project.backend.app.core.resilience import with_llm_resilience

# ------------------------------------------------------------------------
# Layer 0: Custom Exceptions
# ------------------------------------------------------------------------
class CrawlingError(Exception): pass
class BlockedError(CrawlingError): pass
class ExtractionError(CrawlingError): pass
class AllTiersFailedError(CrawlingError): pass

# ------------------------------------------------------------------------
# Layer 1: Observability & Metrics (Prometheus Ready)
# ------------------------------------------------------------------------
logger = logging.getLogger("crawler")
logger.setLevel(logging.INFO)

@dataclass
class CrawlerMetrics:
    requests_total: int = 0
    success_total: int = 0
    waf_blocks_total: int = 0
    retries_total: int = 0
    fallback_llm_total: int = 0

metrics = CrawlerMetrics()

# ------------------------------------------------------------------------
# Layer 2: Advanced Identity & Fingerprint Profiles
# ------------------------------------------------------------------------
FINGERPRINT_PROFILES = [
    # impersonate 타겟과 User-Agent의 버전을 완벽하게 일치시킵니다.
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "impersonate": "chrome124"
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
        "impersonate": "safari16_1"
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "impersonate": "chrome123"
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "impersonate": "chrome120"
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/120.0.0.0 Safari/537.36",
        "impersonate": "edge120"
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "impersonate": "chrome131"
    },
    {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "impersonate": "chrome121"
    }
]

def get_random_fingerprint() -> dict:
    return random.choice(FINGERPRINT_PROFILES)

# ------------------------------------------------------------------------
# Layer 3: Distributed State & Caching Abstraction
# ------------------------------------------------------------------------
class CacheManager:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expirations: Dict[str, float] = {}
        # removed unused _hashes

    async def get(self, key: str) -> Optional[str]:
        if key in self._expirations and self._expirations[key] < time.time():
            self._data.pop(key, None)
            self._expirations.pop(key, None)
            return None
        return self._data.get(key)

    async def set(self, key: str, value: dict, ttl: int = 3600):
        self._data[key] = json.dumps(value)
        if ttl > 0: self._expirations[key] = time.time() + ttl
        
    async def close(self):
        self._data.clear()

cache_manager = CacheManager()

# ------------------------------------------------------------------------
# Layer 4: Proxy & Infrastructure Management
# ------------------------------------------------------------------------
class ProxyManager:
    """Handles rotation, scoring, and eviction of proxies."""
    def __init__(self, raw_proxies: List[str]):
        self.proxies = {p: {"score": 100.0, "uses": 0, "failures": 0} for p in raw_proxies}
        self.lock = asyncio.Lock()

    async def get_proxy(self) -> Optional[str]:
        async with self.lock:
            valid_proxies = [p for p, stats in self.proxies.items() if stats["score"] > 30.0]
            if not valid_proxies:
                return None
            # Weighted random choice based on score
            weights = [self.proxies[p]["score"] for p in valid_proxies]
            chosen = random.choices(valid_proxies, weights=weights, k=1)[0]
            self.proxies[chosen]["uses"] += 1
            return chosen

    async def report(self, proxy: str, success: bool):
        if not proxy or proxy not in self.proxies: return
        async with self.lock:
            if success:
                self.proxies[proxy]["score"] = min(100.0, self.proxies[proxy]["score"] + 5.0)
            else:
                self.proxies[proxy]["score"] -= 15.0
                self.proxies[proxy]["failures"] += 1
                if self.proxies[proxy]["score"] <= 30.0:
                    # metrics.proxy_evictions_total.inc()
                    logger.warning("Proxy evicted due to low score", extra={"proxy": proxy})

# Fallback to single proxy if list not provided
_env_proxy = os.environ.get("RESIDENTIAL_PROXY_URL")
proxy_manager = ProxyManager([_env_proxy] if _env_proxy else [])

# ------------------------------------------------------------------------
# Layer 5: Session & Connection Pooling (Fast Path)
# ------------------------------------------------------------------------
class CurlSessionPool:

    def __init__(self, max_sessions: int = 100):
        self.sessions: Dict[str, requests.AsyncSession] = {}
        self.max_sessions = max_sessions
        self.lock = asyncio.Lock()

    async def get_session(self, domain: str, fingerprint: dict, proxy: Optional[str]) -> requests.AsyncSession:
        async with self.lock:
            key = f"{domain}_{proxy}_{fingerprint['impersonate']}"
            if key not in self.sessions:
                if len(self.sessions) >= self.max_sessions:
                    oldest_key = list(self.sessions.keys())[0]
                    old_client = self.sessions.pop(oldest_key)
                    # Fire and forget cleanup
                    asyncio.create_task(old_client.close())
                
                # Always verify TLS; bypass removed for security reasons
                self.sessions[key] = requests.AsyncSession(
                    timeout=15.0,
                    allow_redirects=True,
                    impersonate=fingerprint["impersonate"],
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    verify=True
                )
            return self.sessions[key]

    async def close_all(self):
        async with self.lock:
            await asyncio.gather(*(client.close() for client in self.sessions.values()), return_exceptions=True)
            self.sessions.clear()

curl_pool = CurlSessionPool()

# ------------------------------------------------------------------------
# Layer 6: Concurrency & Rate Limiting Manager
# ------------------------------------------------------------------------
class DomainRateLimiter:
    def __init__(self, max_concurrent_per_domain: int = 5):
        self._semaphores = defaultdict(lambda: asyncio.Semaphore(max_concurrent_per_domain))

    @asynccontextmanager
    async def acquire(self, url: str):
        domain = urlparse(url).netloc
        async with self._semaphores[domain]:
            await asyncio.sleep(random.uniform(0.05, 0.2)) 
            yield

rate_limiter = DomainRateLimiter(max_concurrent_per_domain=3)

# Global resource blocking handler to avoid per-request allocation
BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet", "websocket"}
async def _route_handler(route):
    try:
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        try:
            await route.continue_()
        except Exception:
            pass


def _normalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = p.scheme or 'https'
    netloc = p.netloc.lower()
    path = p.path or '/'
    return urlunparse((scheme, netloc, path, p.params, p.query, p.fragment))

# ------------------------------------------------------------------------
# Layer 7: Advanced Browser Pool Manager (Queue-based, Self-healing)
# ------------------------------------------------------------------------
@dataclass
class WarmContext:
    context: Any
    created_at: float = field(default_factory=time.time)
    uses: int = 0

class PlaywrightPoolManager:
    """간단하고 안전한 브라우저 풀: 브라우저는 재사용하되, 컨텍스트는 요청마다 새로 생성합니다."""
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self, max_contexts: int = 5, browser_max_age_sec: int = 3600):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.max_contexts = max_contexts
        self._health_check_task: Optional[asyncio.Task] = None
        self._browser_id = uuid.uuid4()
        self._browser_created_at = time.time()
        self.browser_max_age_sec = browser_max_age_sec
        # semaphore to limit concurrent contexts
        self._semaphore = asyncio.Semaphore(max_contexts)

    @classmethod
    async def get_instance(cls):
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                await cls._instance.launch_browser()
            return cls._instance

    async def launch_browser(self):
        async with self._browser_creation_lock:
            if self.browser and self.browser.is_connected():
                return

            logger.info("Launching new browser instance...")
            if self.playwright is None:
                self.playwright = await async_playwright().start()

            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", "--disable-gpu"
                ]
            )
            self._browser_id = uuid.uuid4()
            self._browser_created_at = time.time()
            if not getattr(self.browser, "_disconnect_handler_registered", False):
                self.browser.on("disconnected", self.on_browser_disconnected)
                setattr(self.browser, "_disconnect_handler_registered", True)

            if self._health_check_task is None:
                self._health_check_task = asyncio.create_task(self._run_health_checks())

    def on_browser_disconnected(self):
        logger.error("Browser disconnected unexpectedly! Triggering relaunch.", extra={"browser_id": str(self._browser_id)})
        asyncio.create_task(self.launch_browser())

    async def _run_health_checks(self):
        try:
            while True:
                await asyncio.sleep(60) # Check every minute
                if self.browser is None or not self.browser.is_connected():
                    logger.warning("Health check: Browser is not connected. Relaunching.")
                    self.on_browser_disconnected()
                    continue

                if (time.time() - self._browser_created_at) > self.browser_max_age_sec:
                    logger.info("Browser has reached max age. Proactively recycling.", extra={"browser_id": str(self._browser_id)})
                    old_browser = self.browser
                    self.browser = None
                    asyncio.create_task(self._drain_and_close(old_browser))
                    await self.launch_browser()
        except asyncio.CancelledError:
            logger.info("Health check task cancelled", extra={"browser_id": str(self._browser_id)})
            return

    async def _drain_and_close(self, old_browser: Optional[Browser]):
        if not old_browser: return
        logger.info("Draining old browser...")
        await asyncio.sleep(10)
        try:
            if old_browser.is_connected():
                await old_browser.close()
        except Exception as e:
            logger.error("Error closing drained browser", extra={"error": str(e)})

    async def _create_context(self, proxy: Optional[str] = None) -> WarmContext:
        if not self.browser or not self.browser.is_connected():
            await self.launch_browser()

        profile = get_random_fingerprint()
        context_args = dict(
            user_agent=profile["user_agent"],
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1920, "height": 1080},
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
            bypass_csp=True,
        )
        if proxy:
            # Playwright proxy format
            context_args["proxy"] = {"server": proxy}

        ctx = await self.browser.new_context(**context_args)

        stealth_script = """
        (() => {
            try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); } catch (e) {}
            try { window.chrome = window.chrome || { runtime: {} }; } catch (e) {}
            try { Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] }); } catch (e) {}
            try { const fakePlugin = { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: '' }; Object.defineProperty(navigator, 'plugins', { get: () => [fakePlugin] }); } catch (e) {}
            try { const originalQuery = window.navigator.permissions && window.navigator.permissions.query && window.navigator.permissions.query.bind(window.navigator.permissions); if (originalQuery) { window.navigator.permissions.query = function (params) { if (params && params.name === 'notifications') { return Promise.resolve({ state: Notification.permission }); } return originalQuery(params); }; } } catch (e) {}
            try { const getParameter = WebGLRenderingContext.prototype.getParameter; WebGLRenderingContext.prototype.getParameter = function(parameter) { if (parameter === 37445) return 'Intel Inc.'; if (parameter === 37446) return 'Intel Iris OpenGL Engine'; return getParameter.call(this, parameter); }; } catch (e) {}
            try { const toDataURL = HTMLCanvasElement.prototype.toDataURL; HTMLCanvasElement.prototype.toDataURL = function() { return toDataURL.apply(this, arguments); }; } catch (e) {}
            try { if (window.AudioContext) { const OrigAudioContext = window.AudioContext; window.AudioContext = function() { const ctx = new OrigAudioContext(); return ctx; }; window.AudioContext.prototype = OrigAudioContext.prototype; } } catch (e) {}
        })();
        """

        try:
            await ctx.add_init_script(stealth_script)
        except Exception:
            logger.debug("Failed to add stealth init script to context", extra={"error": "add_init_script failed"})
        return WarmContext(context=ctx)

    @asynccontextmanager
    async def get_context(self, proxy: Optional[str] = None):
        if not self.browser or not self.browser.is_connected():
            await self.launch_browser()

        await self._semaphore.acquire()
        warm_ctx = await self._create_context(proxy)
        try:
            yield warm_ctx.context
        finally:
            try:
                if not warm_ctx.context.is_closed():
                    await warm_ctx.context.close()
            except Exception as e:
                logger.debug("Error closing context", extra={"error": str(e)})
            self._semaphore.release()

    async def shutdown(self, recycle: bool = False):
        logger.info(f"Shutting down browser pool... (Recycle: {recycle})")
        if self._health_check_task and not recycle:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        async with self._browser_creation_lock:
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.debug("Error closing browser on shutdown", extra={"error": str(e)})
                self.browser = None
            if self.playwright and not recycle:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.debug("Error stopping playwright on shutdown", extra={"error": str(e)})
                self.playwright = None

try:
    # playwright-stealth exposes `stealth_async` (preferred) and sometimes `stealth`.
    from playwright_stealth import stealth_async as _ps_stealth_async, stealth as _ps_stealth
except Exception:
    _ps_stealth_async = None
    _ps_stealth = None

async def _apply_playwright_stealth_to_page(page) -> bool:
    """Apply playwright-stealth to the given `page` if available. Returns True on success."""
    try:
        if _ps_stealth_async is not None:
            await _ps_stealth_async(page)
            return True

        if _ps_stealth is not None:
            result = _ps_stealth(page)
            if asyncio.iscoroutine(result):
                await result
            return True
    except Exception as e:
        logger.debug("playwright-stealth apply failed", extra={"error": str(e)})
    return False


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

# ------------------------------------------------------------------------
# Layer 8: Anti-Bot & Extraction Quality Validation
# ------------------------------------------------------------------------
class AntiBotAnalyzer:
    @staticmethod
    def is_blocked(html: str, status: int = 200) -> bool:
        # Rely primarily on status codes and known WAF signatures to reduce false positives
        if status in (401, 403, 429):
            return True
        if not html:
            return False
        html_lower = html.lower()
        signatures = [
            "cf-browser-verification", "just a moment...", "challenge-platform",
            "checking if the site connection is secure", "access denied",
            "datadome", "robot check", "px-captcha", "bot detection", "forbidden"
        ]
        return any(sig in html_lower for sig in signatures)


class QualityValidator:
    @staticmethod
    def calculate_score(data: dict) -> float:
        score = 1.0
        if not data.get("title") or len(data["title"]) < 3: score -= 0.4
        if not data.get("price"): score -= 0.2
        if not data.get("image_url") or "placeholder" in data["image_url"].lower(): score -= 0.4
        return max(0.0, score)

# ------------------------------------------------------------------------
# Layer 9: DOM Reduction (Gemini Token & Cost Explosion Fix)
# ------------------------------------------------------------------------
def _minimize_html_for_llm(html: str) -> str:
    soup = BeautifulSoup(html, 'lxml') # html.parser보다 빠름
    
    # 1. 노이즈 태그 고속 분해
    for tag in soup(['style', 'script', 'svg', 'path', 'nav', 'footer', 'iframe', 'noscript', 'header', 'form', 'button']):
        tag.decompose()
        
    # 2. 주요 본문 컨테이너만 타겟팅하여 추출 범위 축소
    main_content = soup.find('main') or soup.find('article') or soup.find('div', id='content') or soup.find('body') or soup
    
    # 3. 속성 제거 처리를 정규식으로 전환하여 CPU 병목 해결 (class, id, style 등 제거)
    minimized = str(main_content)
    minimized = re.sub(r'\s+(class|id|style|data-[a-zA-Z0-9-]+|onclick|target|rel)="[^"]*"', '', minimized)
    minimized = re.sub(r'\s+', ' ', minimized).strip()
    return minimized[:18000] 

# Gemini Client 싱글톤 관리로 매 요청마다 생성되는 비효율 개선
_gemini_client_instance = None
def _get_gemini_client():
    global _gemini_client_instance
    if _gemini_client_instance is None:
        _gemini_client_instance = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    return _gemini_client_instance

@with_llm_resilience(fallback_default=None)
async def fallback_with_gemini(url: str, html_content: str):
    client = _get_gemini_client()
    
    minimized_html = _minimize_html_for_llm(html_content)

    prompt = f"""
    Extract accurate product information from the provided HTML source of {url}.
    If a value cannot be found, leave it empty. DO NOT guess.
    
    [HTML SOURCE]
    {minimized_html}
    """
    logger.info(f"[{url}] Gemini HTML 기반 폴백 분석 시작 (최적화된 HTML 크기: {len(minimized_html)} chars)")
    
    response = await client.aio.models.generate_content(
        model='gemini-2.5-flash', 
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

# ------------------------------------------------------------------------
# Layer 10: Base Extractors & Core Functions
# ------------------------------------------------------------------------
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
            cleaned_raw = re.sub(r'[\x00-\x1f]', '', raw.strip())
            payload = json.loads(cleaned_raw, strict=False)
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


JSONLD_PATTERN = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)

def _extract_json_ld_via_regex(html: str) -> list[dict]:
    """빠른 경로: 전체 HTML에 대해 정규식으로 JSON-LD 스크립트를 추출하여 파싱합니다.
    BeautifulSoup 생성 비용을 피하기 위해 사용됩니다. 대량 크롤링에서 훨씬 빠릅니다."""
    results: list[dict] = []
    try:
        matches = JSONLD_PATTERN.findall(html)
        for raw in matches:
            try:
                cleaned_raw = re.sub(r'[\x00-\x1f]', '', raw.strip())
                payload = json.loads(cleaned_raw, strict=False)
                candidates = payload if isinstance(payload, list) else [payload]
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    if candidate.get("@type") == "Product":
                        results.append(candidate)
                    elif candidate.get("@graph") and isinstance(candidate.get("@graph"), list):
                        for item in candidate.get("@graph"):
                            if isinstance(item, dict) and item.get("@type") == "Product":
                                results.append(item)
            except Exception:
                continue
    except Exception:
        return []
    return results

def _extract_meta_content(soup: BeautifulSoup, property_name: str) -> str:
    selector = f'meta[property="{property_name}"], meta[name="{property_name}"], meta[itemprop="{property_name}"]'
    meta = soup.select_one(selector)
    if meta and meta.get('content'):
        return _clean_text(meta['content'])
    return ""

# ------------------------------------------------------------------------
# Layer 10: Layered Retry & Network Pipeline
# ------------------------------------------------------------------------
async def _fetch_fast(url: str, proxy: str, fp: dict) -> Tuple[str, str, int]:
    domain = urlparse(url).netloc
    REFERERS = [
        "https://www.google.com/",
        "https://search.naver.com/",
        "https://www.bing.com/",
        "https://m.search.naver.com/",
    ]
    client = await curl_pool.get_session(domain, fp, proxy)
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": fp["user_agent"],
        "referer": random.choice(REFERERS),
    }
    response = await client.get(url, headers=headers)
    return response.text, str(response.url), response.status_code

async def _fetch_browser(url: str, proxy: str) -> Tuple[str, str]:
    pool_manager = await PlaywrightPoolManager.get_instance()
    async with pool_manager.get_context(proxy=proxy) as context:
        page = await context.new_page()
        # playwright-stealth가 설치되어 있다면 페이지에 적용 시도
        try:
            applied = await _apply_playwright_stealth_to_page(page)
            if applied:
                logger.debug("Applied playwright-stealth to page", extra={"url": url})
        except Exception:
            logger.debug("playwright-stealth application raised", extra={"url": url})
        try:
            # 타임아웃 최적화 (쇼핑몰의 불필요한 서드파티 추적 스크립트 대기 방지)
            page.set_default_navigation_timeout(20000)
            page.set_default_timeout(10000)
            
            # 네트워크 비용 및 속도 최적화를 위한 에셋 차단 확장
            await page.route("**/*", _route_handler)
            
            # WAF 대응: domcontentloaded 대신 networkidle를 사용하되 제한시간을 짧게 가져감
            response = await page.goto(url, wait_until="commit") 
            try:
                # 상품 정보 구조가 잡힐 때까지만 타겟 대기 (시간 단축 핵심)
                await page.wait_for_selector("meta[property='og:title']", timeout=3000)
            except:
                await page.wait_for_load_state("domcontentloaded")
            
            html = await page.content()
            return html, page.url
        finally:
            await page.close()

async def _execute_fetch_pipeline(url: str) -> dict:
    """Executes a tiered fallback strategy for maximum success rate."""
    metrics.requests_total += 1
    fp = get_random_fingerprint()
    proxy = await proxy_manager.get_proxy()

    # Tier 1: Fast Path (curl-cffi)
    try:
        html, final_url, status = await _fetch_fast(url, proxy, fp)
        if not AntiBotAnalyzer.is_blocked(html, status):
            await proxy_manager.report(proxy, True)
            metrics.success_total += 1
            return {"html": html, "finalUrl": final_url}
        
        metrics.waf_blocks_total += 1
        await proxy_manager.report(proxy, False)
        logger.warning(f"Fast path blocked (status {status}), falling back to browser.", extra={"url": url})
    except Exception as e:
        metrics.retries_total += 1
        await proxy_manager.report(proxy, False)
        logger.warning("Fast path failed, falling back to browser.", extra={"url": url, "error": str(e)})

    # Tier 2: Browser Path (Playwright)
    proxy = await proxy_manager.get_proxy()
    try:
        html, final_url = await _fetch_browser(url, proxy)
        metrics.success_total += 1
        return {"html": html, "finalUrl": final_url}
    except Exception as e:
        metrics.retries_total += 1
        await proxy_manager.report(proxy, False)
        logger.error("Browser tier failed", extra={"url": url, "error": str(e)})
        raise AllTiersFailedError(f"All network fetch tiers exhausted for {url}")

def _extract_framework_data(soup: BeautifulSoup) -> dict:
    """Next.js (__NEXT_DATA__) 및 Nuxt.js 전용 데이터 추출"""
    data = {}
    next_script = soup.find("script", id="__NEXT_DATA__")
    if next_script and next_script.string:
        try:
            payload = json.loads(next_script.string)
            props = payload.get("props", {}).get("pageProps", {})
            product = props.get("product") or props.get("item") or props.get("initialState", {}).get("product")
            if isinstance(product, dict):
                data["title"] = product.get("name") or product.get("title")
                data["price"] = product.get("price")
                data["brand"] = product.get("brand")
                if "images" in product and product["images"]:
                    img = product["images"][0]
                    data["image_url"] = img.get("url") if isinstance(img, dict) else img
        except Exception as e:
            logger.debug("_extract_framework_data JSON parse failed", extra={"error": str(e)})
    ssr_script = soup.find("script", {"data-n-head": "ssr"})
    if ssr_script and ssr_script.string and "window.__NUXT__" in ssr_script.string:
        try:
            title_match = re.search(r'title\s*:\s*["\'](.+?)["\']', ssr_script.string)
            if title_match: data["title"] = title_match.group(1)
        except Exception as e:
            logger.debug("_extract_framework_data Nuxt parse failed", extra={"error": str(e)})
    return {k: v for k, v in data.items() if v}

# ------------------------------------------------------------------------
# Layer 11: Site-Specific Extractor Plugins
# ------------------------------------------------------------------------
class SiteExtractor:
    """도메인별 특화 크롤링 훅을 제공하는 베이스 클래스"""
    def extract(self, url: str, soup: BeautifulSoup, data: dict) -> dict:
        return data

class BunjangExtractor(SiteExtractor):
    def extract(self, url: str, soup: BeautifulSoup, data: dict) -> dict:
        if "번개장터" in data.get("title", "") or data.get("title", "") == "취향을 잇는 거래":
            data["title"] = "" 
        if "중고거래" in data.get("description", "") or "번개장터" in data.get("description", ""):
            data["description"] = ""
        img = data.get("image_url", "").lower()
        if "logo" in img or "bg_icon" in img:
            data["image_url"] = ""
        return data

EXTRACTOR_REGISTRY: Dict[str, Type[SiteExtractor]] = {
    "bunjang.co.kr": BunjangExtractor,
    "bjn.co.kr": BunjangExtractor,
}

# ------------------------------------------------------------------------
# Layer 12: Distributed-Ready Facade
# ------------------------------------------------------------------------
async def scrape_product_metadata(url: str) -> dict:
    
    normalized_key = _normalize_url(url)
    cached_result = await cache_manager.get(normalized_key)
    if cached_result:
        try:
            cached_result = json.loads(cached_result)
            metrics.success_total += 1
            return {**cached_result, "source": "cache"}
        except: pass

    async with rate_limiter.acquire(url):
        final_url = url
        html = "" 

        try:
            page_data = await _execute_fetch_pipeline(url)
            html = page_data["html"]
            final_url = page_data["finalUrl"]

            # 빠른 경로: 정규식으로 JSON-LD만 먼저 추출하여 파싱합니다 (BeautifulSoup 생략)
            try:
                regex_products = _extract_json_ld_via_regex(html)
                if regex_products:
                    prod = regex_products[0]
                    offers = prod.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    images = prod.get("image", [])
                    if isinstance(images, str):
                        images = [images]

                    price = _clean_text(str(offers.get("price") or ""))
                    currency = _clean_text(str(offers.get("priceCurrency") or "KRW"))
                    availability = _clean_text(str(offers.get("availability") or "")).split('/')[-1]
                    title = _clean_text(prod.get("name") or prod.get("title") or "")
                    image_url = _clean_text(images[0]) if images else ""
                    description = _clean_text(prod.get("description") or "")
                    brand = _clean_text(prod.get("brand", {}).get("name") if isinstance(prod.get("brand"), dict) else str(prod.get("brand") or ""))
                    normalized_image_url = urljoin(final_url, image_url) if image_url else ""

                    extracted_data = {
                        "url": final_url,
                        "title": title,
                        "brand": brand,
                        "price": price,
                        "currency": currency,
                        "availability": availability,
                        "image_url": normalized_image_url,
                        "description": description,
                        "source": "json-ld-regex",
                    }

                    quality_score = QualityValidator.calculate_score(extracted_data)
                    if quality_score >= 0.7:
                        logger.info("Fast JSON-LD regex extraction succeeded", extra={"score": quality_score, "url": url})
                        metrics.success_total += 1
                        await cache_manager.set(_normalize_url(final_url), extracted_data)
                        return extracted_data
            except Exception as e:
                logger.debug("JSON-LD regex fast path failed", extra={"url": url, "error": str(e)})

            soup = BeautifulSoup(html, 'lxml')
            
            # 1. Framework & Base Extraction
            framework_data = _extract_framework_data(soup)
            products = _extract_json_ld_products(soup)
            product = products[0] if products else {}

            offers = product.get("offers", {})
            if isinstance(offers, list): offers = offers[0] if offers else {}
            images = product.get("image", [])
            if isinstance(images, str): images = [images]

            price = framework_data.get("price") or _clean_text(str(offers.get("price") or _extract_meta_content(soup, "product:price:amount") or _extract_meta_content(soup, "og:price:amount")))
            currency = _clean_text(str(offers.get("priceCurrency") or _extract_meta_content(soup, "product:price:currency") or _extract_meta_content(soup, "og:price:currency") or "KRW"))
            availability = _clean_text(str(offers.get("availability") or "")).split("/")[-1]
            
            title = framework_data.get("title") or (_clean_text(product.get("name") or "") or _extract_meta_content(soup, "og:title") or (soup.find("title").get_text(strip=True) if soup.find("title") else ""))
            
            image_url = framework_data.get("image_url") or (_clean_text(images[0] if images else "") or _extract_meta_content(soup, "og:image") or _extract_meta_content(soup, "twitter:image") or _extract_meta_content(soup, "image"))
            if not image_url:
                for selector in ["img[id*='product']", "img[class*='product']", ".product-image img"]:
                    img_tag = soup.select_one(selector)
                    if img_tag and img_tag.get("src"):
                        image_url = img_tag["src"]
                        break

            description = (_clean_text(product.get("description") or "") or _extract_meta_content(soup, "og:description") or _extract_meta_content(soup, "description"))
            brand = framework_data.get("brand") or _clean_text(product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else str(product.get("brand") or ""))
            normalized_image_url = urljoin(final_url, image_url) if image_url else ""

            extracted_data = {
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

            # 2. Site-Specific Plugin Overrides
            domain = urlparse(final_url).netloc.replace("www.", "")
            extractor_cls = next((ext for key, ext in EXTRACTOR_REGISTRY.items() if key in domain), SiteExtractor)
            extracted_data = extractor_cls().extract(final_url, soup, extracted_data)

            # 3. Gemini Fallback Check
            quality_score = QualityValidator.calculate_score(extracted_data)
            if quality_score < 0.7:
                logger.info("Extraction quality low, triggering LLM fallback", extra={"score": quality_score, "url": url})
                
                if AntiBotAnalyzer.is_blocked(html):
                    raise BlockedError("WAF block detected")
                
                gemini_result = await fallback_with_gemini(url, html) 
                if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                    metrics.fallback_llm_total += 1
                    await cache_manager.set(_normalize_url(final_url), gemini_result)
                    return gemini_result

            await cache_manager.set(_normalize_url(final_url), extracted_data)
            return extracted_data
        except Exception as e:
            logger.error("Extraction pipeline failed", extra={"url": url, "error": str(e)})
            if html and len(html.strip()) > 100:
                if AntiBotAnalyzer.is_blocked(html):
                    raise ValueError("Blocked by WAF.")
                
                gemini_result = await fallback_with_gemini(url, html)
                if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                    metrics.fallback_llm_total += 1
                    await cache_manager.set(_normalize_url(final_url), gemini_result)
                    return gemini_result
            raise ValueError("Extraction failed.")

# ------------------------------------------------------------------------
# Resource Cleanup Hooks (Call these on Fastapi lifespan shutdown)
# ------------------------------------------------------------------------
async def cleanup_crawler_resources():
    logger.info("Cleaning up crawler resources...")
    await curl_pool.close_all()
    try:
        pool = await PlaywrightPoolManager.get_instance()
        await pool.shutdown()
    except Exception as e:
        logger.error("Error shutting down browser pool", extra={"error": str(e)})
