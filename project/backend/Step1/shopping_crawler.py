import os
import re
import json
import uuid
import time
import random
import asyncio
import logging
import hashlib
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Type, List, Tuple, Protocol
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from pydantic import BaseModel,Field
import curl_cffi.requests as requests
from google import genai
from google.genai import types
from playwright.async_api import async_playwright, Browser
from playwright_stealth import Stealth
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
class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename', 'funcName', 
            'levelname', 'levelno', 'lineno', 'message', 'module', 'msecs', 'msg', 'name', 
            'pathname', 'process', 'processName', 'relativeCreated', 'stack_info', 'thread', 
            'threadName', 'taskName'
        }
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_record[key] = value
        return json.dumps(log_record)

logger = logging.getLogger("crawler")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Prometheus-client can be used here to define actual metrics
@dataclass
class CrawlerMetrics:
    requests_total: int = 0
    success_total: int = 0
    cache_hits: int = 0
    waf_blocks_total: int = 0
    retries_total: int = 0
    fallback_llm_total: int = 0

metrics = CrawlerMetrics()

# ------------------------------------------------------------------------
# Layer 2: Advanced Identity & Fingerprint Profiles
# ------------------------------------------------------------------------
FINGERPRINT_PROFILES = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
        "viewport": {"width": 1920, "height": 1080},
        "impersonate": "chrome124",
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="123", "Google Chrome";v="123", "Not:A-Brand";v="8"',
        "platform": '"macOS"',
        "viewport": {"width": 1440, "height": 900},
        "impersonate": "chrome120", # closest fallback in curl_cffi
        "hardwareConcurrency": 10,
        "deviceMemory": 16,
    }
]

def get_random_fingerprint() -> dict:
    profile = random.choice(FINGERPRINT_PROFILES).copy()
    profile["locale"] = "ko-KR"
    profile["timezone_id"] = "Asia/Seoul"
    return profile

# ------------------------------------------------------------------------
# Layer 3: Distributed State & Caching Abstraction
# ------------------------------------------------------------------------
class DistributedStateBackend(Protocol):
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: int): ...
    async def hgetall(self, name: str) -> Dict[str, str]: ...
    async def hset(self, name: str, mapping: Dict[str, Any]): ...
    async def hincrby(self, name: str, key: str, amount: int): ...
    async def close(self): ...

class InMemoryBackend(DistributedStateBackend):
    """For local development and testing without Redis."""
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expirations: Dict[str, float] = {}
        self._hashes: Dict[str, Dict[str, str]] = defaultdict(dict)

    async def get(self, key: str) -> Optional[str]:
        if key in self._expirations and self._expirations[key] < time.time():
            self._data.pop(key, None)
            self._expirations.pop(key, None)
            return None
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl: int):
        self._data[key] = value
        if ttl > 0: self._expirations[key] = time.time() + ttl

    async def hgetall(self, name: str) -> Dict[str, str]:
        return self._hashes.get(name, {})

    async def hset(self, name: str, mapping: Dict[str, Any]):
        self._hashes[name].update(mapping)

    async def hincrby(self, name: str, key: str, amount: int):
        current = int(self._hashes[name].get(key, "0"))
        self._hashes[name][key] = str(current + amount)

    async def close(self): pass

class CacheManager:
    def __init__(self, backend: DistributedStateBackend, prefix: str = "crawler_cache"):
        self.backend = backend
        self.prefix = prefix

    async def get(self, key: str) -> Optional[dict]:
        cache_key = f"{self.prefix}:{hashlib.sha256(key.encode()).hexdigest()}"
        cached = await self.backend.get(cache_key)
        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: dict, ttl: int = 3600):
        cache_key = f"{self.prefix}:{hashlib.sha256(key.encode()).hexdigest()}"
        await self.backend.set(cache_key, json.dumps(value), ttl)

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
    """Maintains persistent TLS connections per domain to eliminate handshake overhead."""
    # 실제 운영에서 전체 verify=False는 위험하므로, 차단이 심한 도메인만 선택적 Bypass 설정
    TLS_BYPASS_DOMAINS = {"bunjang.co.kr", "bjn.co.kr", "musinsa.com"}

    def __init__(self, max_sessions: int = 50):
        self.sessions: Dict[str, requests.AsyncSession] = {}
        self.max_sessions = max_sessions
        self.lock = asyncio.Lock()

    async def get_session(self, domain: str, fingerprint: dict, proxy: Optional[str]) -> requests.AsyncSession:
        async with self.lock:
            key = f"{domain}_{proxy}_{fingerprint['impersonate']}"
            if key not in self.sessions:
                if len(self.sessions) >= self.max_sessions:
                    oldest_key = next(iter(self.sessions))
                    old_client = self.sessions.pop(oldest_key)
                    # Fire and forget cleanup
                    asyncio.create_task(old_client.close())
                
                base_domain = domain.replace("www.", "")
                verify_tls = base_domain not in self.TLS_BYPASS_DOMAINS
                self.sessions[key] = requests.AsyncSession(
                    timeout=15.0,
                    allow_redirects=True,
                    impersonate=fingerprint["impersonate"],
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    verify=verify_tls 
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
    def __init__(self, max_concurrent_per_domain: int = 3):
        self._semaphores = defaultdict(lambda: asyncio.Semaphore(max_concurrent_per_domain))

    @asynccontextmanager
    async def acquire(self, url: str):
        domain = urlparse(url).netloc
        async with self._semaphores[domain]:
            await asyncio.sleep(random.uniform(0.2, 0.7)) # Jitter
            yield

rate_limiter = DomainRateLimiter(max_concurrent_per_domain=3)

# ------------------------------------------------------------------------
# Layer 7: Advanced Browser Pool Manager (Queue-based, Self-healing)
# ------------------------------------------------------------------------
@dataclass
class WarmContext:
    context: Any
    uses: int = 0
    created_at: float = field(default_factory=time.time)
    fingerprint: dict = field(default_factory=dict)
    proxy: Optional[str] = None

class PlaywrightPoolManager:
    """Queue-based, self-healing browser pool manager."""
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self, max_contexts: int = 5, browser_max_age_sec: int = 3600):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.max_contexts = max_contexts
        self.context_queue: asyncio.Queue[WarmContext] = asyncio.Queue(max_contexts)
        self._browser_creation_lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._browser_id = uuid.uuid4()
        self._browser_created_at = time.time()
        self.browser_max_age_sec = browser_max_age_sec

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
                    "--no-sandbox", "--disable-dev-shm-usage"
                ]
            )
            self._browser_id = uuid.uuid4()
            self._browser_created_at = time.time()
            if not getattr(self.browser, "_disconnect_handler_registered", False):
                self.browser.on("disconnected", self.on_browser_disconnected)
                setattr(self.browser, "_disconnect_handler_registered", True)

            if self._health_check_task is None:
                self._health_check_task = asyncio.create_task(self._run_health_checks())

            # Pre-warm contexts (데드락 방지 및 즉시 사용 가능 상태 유지)
            while not self.context_queue.empty():
                try:
                    self.context_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            contexts = await asyncio.gather(
                *(self._create_context(None) for _ in range(self.max_contexts))
            )
            for ctx in contexts:
                self.context_queue.put_nowait(ctx)

    def on_browser_disconnected(self):
        logger.error("Browser disconnected unexpectedly! Triggering relaunch.", extra={"browser_id": str(self._browser_id)})
        # Clear queue to prevent using contexts from dead browser
        while not self.context_queue.empty():
            try:
                self.context_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        asyncio.create_task(self.launch_browser())

    async def _run_health_checks(self):
        while True:
            await asyncio.sleep(60) # Check every minute
            if self.browser is None or not self.browser.is_connected():
                logger.warning("Health check: Browser is not connected. Relaunching.")
                self.on_browser_disconnected()
                continue

            if (time.time() - self._browser_created_at) > self.browser_max_age_sec:
                logger.info("Browser has reached max age. Proactively recycling.", extra={"browser_id": str(self._browser_id)})
                # Atomic switch: 기존 브라우저는 안전하게 draining 처리 후 백그라운드 교체
                old_browser = self.browser
                self.browser = None
                asyncio.create_task(self._drain_and_close(old_browser))
                await self.launch_browser()

    async def _drain_and_close(self, old_browser: Optional[Browser]):
        if not old_browser: return
        logger.info("Draining old browser...")
        await asyncio.sleep(10) # 진행 중인 작업이 완료될 수 있도록 유예 시간 제공
        try:
            if old_browser.is_connected():
                await old_browser.close()
        except Exception as e:
            logger.error("Error closing drained browser", extra={"error": str(e)})

    async def _create_context(self, proxy: Optional[str]) -> WarmContext:
        fp = get_random_fingerprint()

        browser = self.browser
        if not browser or not browser.is_connected():
            await self.launch_browser()
            browser = self.browser

        ctx = await browser.new_context(
            **{k: v for k, v in fp.items() if k in ["user_agent", "viewport", "locale", "timezone_id"]},
            java_script_enabled=True,
        )
        platform_val = fp.get('platform', '"Windows"').strip('"')
        nav_platform = 'Win32' if platform_val == 'Windows' else 'MacIntel'
        # Advanced fingerprinting
        await ctx.add_init_script(f"""
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {fp['hardwareConcurrency']}}});
            Object.defineProperty(navigator, 'deviceMemory', {{get: () => {fp['deviceMemory']}}});
            Object.defineProperty(navigator, 'platform', {{get: () => '{nav_platform}'}});
            Object.defineProperty(navigator, 'languages', {{get: () => ['ko-KR', 'ko']}});
            window.chrome = {{runtime: {{}}}};
        """)
        return WarmContext(context=ctx, fingerprint=fp, proxy=None)

    @asynccontextmanager
    async def get_context(self, proxy: Optional[str] = None):
        if not self.browser or not self.browser.is_connected():
            await self.launch_browser()
            
        warm_ctx = await asyncio.wait_for(self.context_queue.get(),timeout=10)
        # 요청한 Proxy와 Pre-warm된 Proxy 환경이 다르면 새로 교체
        try:
            warm_ctx.uses += 1
            yield warm_ctx.context
        finally:
            # Recycle logic: Destroy if used > 20 times or older than 10 mins to clear cache/leaks
            if warm_ctx.uses > 20 or (time.time() - warm_ctx.created_at) > 600 or warm_ctx.context.is_closed():
                if not warm_ctx.context.is_closed():
                    await warm_ctx.context.close()
                # Refill the queue with a fresh context
                new_ctx = await self._create_context(proxy)
                try:
                    self.context_queue.put_nowait(new_ctx)
                except asyncio.QueueFull:
                    await new_ctx.context.close()
            else:
                self.context_queue.put_nowait(warm_ctx)

    async def shutdown(self, recycle: bool = False):
        logger.info(f"Shutting down browser pool... (Recycle: {recycle})")
        if self._health_check_task and not recycle:
            self._health_check_task.cancel()
            self._health_check_task = None

        while not self.context_queue.empty():
            ctx = self.context_queue.get_nowait()
            await ctx.context.close()

        async with self._browser_creation_lock:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright and not recycle:
                await self.playwright.stop()
                self.playwright = None

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
        if status in (403, 429): return True
        if not html: return False
        
        html_lower = html.lower()
        signatures = [
            "cf-browser-verification", "just a moment...", "challenge-platform",
            "checking if the site connection is secure", "access denied", 
            "datadome", "robot check", "px-captcha"
        ]
        if any(sig in html_lower for sig in signatures): return True
        
        # Entropy check: if body is too small but script is huge (JS challenge)
        if len(html) < 2000 and "window.location=" in html_lower:
            return True
            
        return False

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
    
    # 불필요한 노이즈 태그 완벽 제거
    for tag in soup(['style', 'svg', 'path', 'nav', 'footer', 'iframe', 'noscript', 'form', 'button', 'header']):
        tag.decompose()
        
    # 스크립트는 JSON-LD만 남기고 모두 제거
    for tag in soup('script'):
        if tag.get('type') != 'application/ld+json':
            tag.decompose()
            
    # LLM이 파싱하는 데 불필요한 속성 제거 (id, class, src, href, property, content만 유지)
    allowed_attrs = {'id', 'class', 'src', 'href', 'property', 'content', 'itemprop'}
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        for attr in attrs:
            if attr not in allowed_attrs:
                del tag[attr]
                
    # 메인 컨텐츠 영역만 추출 시도
    main_content = soup.find('main') or soup.find('article') or soup.find('body') or soup
    minimized = str(main_content)
    minimized = re.sub(r'>\s+<', '><', minimized) # 공백 압축
    return minimized[:20000] # 최후 방어선 (약 5000토큰 이내 제한)

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
    client = await curl_pool.get_session(domain, fp, proxy)
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': f'{fp["locale"]},en-US;q=0.9,en;q=0.8',
        'sec-ch-ua': fp['sec_ch_ua'],
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': fp['platform'],
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'upgrade-insecure-requests': '1',
        'user-agent': fp["user_agent"],
    }
    response = await client.get(url, headers=headers)
    return response.text, str(response.url), response.status_code

async def _fetch_browser(url: str, proxy: str) -> Tuple[str, str]:
    pool_manager = await PlaywrightPoolManager.get_instance()
    async with pool_manager.get_context(proxy=proxy) as context:
        page = await context.new_page()
        try:
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
                    
            # Efficient aggressive resource blocking
            async def abort_route(route):
                await route.abort()
                
            await page.route("**/*.{png,jpg,jpeg,webp,gif,woff,woff2,mp4}", abort_route)
            
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            try:
                await page.locator("body").wait_for(timeout=10000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            
            html = await page.content()
            return html, page.url
        finally:
            await page.close()

async def _execute_fetch_pipeline(url: str) -> dict:
    """Executes a tiered fallback strategy for maximum success rate."""
    fp = get_random_fingerprint()
    
    for attempt in range(1, 3):
        proxy = await proxy_manager.get_proxy()
        try:
            if attempt == 1:
                # Tier 1: Fast Session Pooling HTTP
                html, final_url, status = await _fetch_fast(url, proxy, fp)
                if AntiBotAnalyzer.is_blocked(html, status):
                    metrics.waf_blocks_total += 1
                    await proxy_manager.report(proxy, False)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    continue # Trigger next tier
                await proxy_manager.report(proxy, True)
                metrics.success_total += 1
                return {"html": html, "finalUrl": final_url}
            else:
                # Tier 2: Browser Fallback
                html, final_url = await _fetch_browser(url, proxy)
                metrics.success_total += 1
                return {"html": html, "finalUrl": final_url}
        except Exception as e:
            metrics.retries_total += 1
            await proxy_manager.report(proxy, False)
            logger.warning("Fetch tier failed", extra={"url": url, "attempt": attempt, "error": str(e)})
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
    raise Exception("All network fetch tiers exhausted.")

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
async def scrape_product_metadata(url: str, cache: Optional[CacheManager] = None) -> dict:
    logger.info("Extraction pipeline start", extra={"url": url})
    metrics.requests_total += 1
    
    # Pipeline 통합: Cache Hit 검증
    if cache:
        cached_result = await cache.get(url)
        if cached_result:
            logger.info("Cache hit", extra={"url": url})
            metrics.cache_hits += 1
            metrics.success_total += 1
            return {**cached_result, "source": "cache"}

    async with rate_limiter.acquire(url):
        final_url = url
        html = "" 

        try:
            page_data = await _execute_fetch_pipeline(url)
            html = page_data["html"]
            final_url = page_data["finalUrl"]
            
            soup = BeautifulSoup(html, 'lxml')
            
            # 1. Base Extraction
            products = _extract_json_ld_products(soup)
            product = products[0] if products else {}

            offers = product.get("offers", {})
            if isinstance(offers, list): offers = offers[0] if offers else {}
            images = product.get("image", [])
            if isinstance(images, str): images = [images]

            price = _clean_text(str(offers.get("price") or _extract_meta_content(soup, "product:price:amount") or _extract_meta_content(soup, "og:price:amount")))
            currency = _clean_text(str(offers.get("priceCurrency") or _extract_meta_content(soup, "product:price:currency") or _extract_meta_content(soup, "og:price:currency")))
            availability = _clean_text(str(offers.get("availability") or "")).split("/")[-1]
            
            title = (_clean_text(product.get("name") or "") or _extract_meta_content(soup, "og:title") or (soup.find("title").get_text(strip=True) if soup.find("title") else ""))
            
            image_url = (_clean_text(images[0] if images else "") or _extract_meta_content(soup, "og:image") or _extract_meta_content(soup, "twitter:image") or _extract_meta_content(soup, "image"))
            if not image_url:
                for selector in ["img[id*='product']", "img[class*='product']", ".product-image img"]:
                    img_tag = soup.select_one(selector)
                    if img_tag and img_tag.get("src"):
                        image_url = img_tag["src"]
                        break

            description = (_clean_text(product.get("description") or "") or _extract_meta_content(soup, "og:description") or _extract_meta_content(soup, "description"))
            brand = _clean_text(product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else str(product.get("brand") or ""))
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
                    raise ValueError("WAF block detected, skipping LLM fallback.")
                
                gemini_result = await fallback_with_gemini(url, html) 
                if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                    metrics.fallback_llm_total += 1
                    if cache:
                        await cache.set(url, gemini_result)
                    return gemini_result

            if cache:
                await cache.set(url, extracted_data)
            return extracted_data

        except Exception as e:
            logger.error("Extraction pipeline failed", extra={"url": url, "error": str(e)})
            if html and len(html.strip()) > 100:
                if AntiBotAnalyzer.is_blocked(html):
                    raise ValueError("Blocked by WAF.")
                
                gemini_result = await fallback_with_gemini(url, html)
                if gemini_result and gemini_result.get("title") and gemini_result.get("image_url"):
                    metrics.fallback_llm_total += 1
                    if cache:
                        await cache.set(url, gemini_result)
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
