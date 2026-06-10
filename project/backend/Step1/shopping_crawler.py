import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type
from urllib.parse import parse_qs, urljoin, urlparse

import curl_cffi.requests as requests
import jmespath
import orjson
from selectolax.parser import HTMLParser, Node

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
    api_discovery_total: int = 0
    hydration_total: int = 0
    structured_data_total: int = 0

metrics = CrawlerMetrics()

# ------------------------------------------------------------------------
# Layer 2: Fetch Replay Identity Profiles
# ------------------------------------------------------------------------
# curl-cffi can align TLS/HTTP2 fingerprints through ``impersonate``, but it
# does not execute JavaScript. Keep this layer honest: these profiles provide
# coherent request headers and cookie continuity only; they are not a substitute
# for navigator/screen/canvas/WebGL/audio signals on high-friction WAFs.
FETCH_REPLAY_PROFILES = [
    {
        "name": "chrome-windows",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "impersonate": "chrome124",
        "headers": {
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    },
    {
        "name": "chrome-macos",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "impersonate": "chrome124",
        "headers": {
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        },
    },
    {
        "name": "safari-macos",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        "impersonate": "safari_18_0",
        "headers": {},
    },
]


def get_random_fingerprint() -> dict:
    return random.choice(FETCH_REPLAY_PROFILES).copy()

# ------------------------------------------------------------------------
# Layer 3: Distributed State & Caching Abstraction
# ------------------------------------------------------------------------
class CacheManager:
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

    async def set(self, key: str, value: dict, ttl: int = 3600):
        self._data[key] = orjson.dumps(value).decode("utf-8")
        if ttl > 0:
            self._expirations[key] = time.time() + ttl

    async def close(self):
        self._data.clear()

cache_manager = CacheManager()

# ------------------------------------------------------------------------
# Layer 4: Proxy & Infrastructure Management
# ------------------------------------------------------------------------
class ProxyClass(str, Enum):
    GENERIC = "generic"
    CLOUDFLARE = "cloudflare"
    DATADOME = "datadome"
    AKAMAI = "akamai"
    PERIMETERX = "perimeterx"
    KASADA = "kasada"
    IMPERVA = "imperva"
    SHAPE = "shape"


class ProxyNetwork(str, Enum):
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    DATACENTER = "datacenter"


@dataclass
class ProxyStats:
    network: ProxyNetwork = ProxyNetwork.RESIDENTIAL
    reputation_score: float = 0.75
    ewma_latency_ms: float = 750.0
    successes: int = 1
    failures: int = 1
    blocks: int = 0
    uses: int = 0
    last_seen: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        return self.successes / max(1, self.successes + self.failures)

    @property
    def block_rate(self) -> float:
        return self.blocks / max(1, self.uses)

    @property
    def latency_score(self) -> float:
        return max(0.0, min(1.0, 1.0 - (self.ewma_latency_ms / 5000.0)))

    @property
    def score(self) -> float:
        # IP reputation and network class are more predictive than raw latency
        # for Korean shopping domains. Latency remains a tie-breaker only.
        block_score = 1.0 - self.block_rate
        return (0.4 * self.reputation_score) + (0.3 * self.success_rate) + (0.2 * block_score) + (0.1 * self.latency_score)


class ProxyManager:
    """Routes by network quality first (mobile/residential/datacenter), then WAF pool health."""
    def __init__(self, raw_proxies: List[str]):
        self.proxies: Dict[ProxyNetwork, Dict[ProxyClass, Dict[str, ProxyStats]]] = {
            network: {klass: {} for klass in ProxyClass} for network in ProxyNetwork
        }
        self.lock = asyncio.Lock()
        for raw in raw_proxies:
            if raw:
                self.add_proxy(raw, ProxyNetwork.RESIDENTIAL)

    def add_proxy(self, proxy: str, network: ProxyNetwork = ProxyNetwork.RESIDENTIAL, proxy_class: ProxyClass = ProxyClass.GENERIC, reputation_score: Optional[float] = None):
        if reputation_score is None:
            reputation_score = {
                ProxyNetwork.MOBILE: 0.95,
                ProxyNetwork.RESIDENTIAL: 0.85,
                ProxyNetwork.DATACENTER: 0.25,
            }[network]
        self.proxies.setdefault(network, {}).setdefault(proxy_class, {})[proxy] = ProxyStats(network=network, reputation_score=reputation_score)

    async def get_proxy(self, proxy_class: ProxyClass = ProxyClass.GENERIC, network: ProxyNetwork = ProxyNetwork.RESIDENTIAL) -> Optional[str]:
        async with self.lock:
            class_pool = self.proxies.get(network, {}).get(proxy_class, {})
            generic_pool = self.proxies.get(network, {}).get(ProxyClass.GENERIC, {})
            candidates = class_pool or generic_pool

            # Never silently downgrade high-friction domains to datacenter. If
            # mobile/residential is empty, return None so caller can fail fast or
            # choose a browser/API worker instead of burning bad IP reputation.
            valid = [(proxy, stats) for proxy, stats in candidates.items() if stats.score >= 0.25]
            if not valid:
                return None
            chosen = random.choices([p for p, _ in valid], weights=[s.score for _, s in valid], k=1)[0]
            candidates[chosen].uses += 1
            candidates[chosen].last_seen = time.time()
            return chosen

    async def report(
        self,
        proxy: Optional[str],
        success: bool,
        latency_ms: Optional[float] = None,
        blocked: bool = False,
        proxy_class: ProxyClass = ProxyClass.GENERIC,
        network: ProxyNetwork = ProxyNetwork.RESIDENTIAL,
    ):
        if not proxy:
            return
        async with self.lock:
            stats = self.proxies.setdefault(network, {}).setdefault(proxy_class, {}).get(proxy)
            if not stats:
                stats = self.proxies.setdefault(network, {}).setdefault(ProxyClass.GENERIC, {}).get(proxy)
            if not stats:
                return
            if success:
                stats.successes += 1
                stats.reputation_score = min(1.0, stats.reputation_score + 0.01)
            else:
                stats.failures += 1
                stats.reputation_score = max(0.0, stats.reputation_score - (0.12 if blocked else 0.03))
            if blocked:
                stats.blocks += 1
            if latency_ms is not None:
                stats.ewma_latency_ms = (0.8 * stats.ewma_latency_ms) + (0.2 * latency_ms)
            if stats.score < 0.25:
                logger.warning("Proxy score below active threshold", extra={"proxy": proxy, "score": stats.score, "class": proxy_class.value, "network": network.value})


def _split_proxy_env(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [proxy.strip() for proxy in re.split(r"[,\n]", value) if proxy.strip()]


proxy_manager = ProxyManager([])
for _proxy in _split_proxy_env(os.environ.get("RESIDENTIAL_PROXY_URLS") or os.environ.get("RESIDENTIAL_PROXY_URL")):
    proxy_manager.add_proxy(_proxy, ProxyNetwork.RESIDENTIAL)
for _proxy in _split_proxy_env(os.environ.get("MOBILE_PROXY_URLS") or os.environ.get("MOBILE_PROXY_URL")):
    proxy_manager.add_proxy(_proxy, ProxyNetwork.MOBILE)
for _proxy in _split_proxy_env(os.environ.get("DATACENTER_PROXY_URLS") or os.environ.get("DATACENTER_PROXY_URL")):
    proxy_manager.add_proxy(_proxy, ProxyNetwork.DATACENTER)

# ------------------------------------------------------------------------
# Layer 5: Session & Connection Pooling (Fetch Replay Fast Path)
# ------------------------------------------------------------------------
class CurlSessionPool:
    TLS_BYPASS_DOMAINS = {"bunjang.co.kr", "bjn.co.kr", "musinsa.com", "www.musinsa.com"}

    def __init__(self, max_sessions: int = 100):
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
                    asyncio.create_task(old_client.close())

                base_domain = domain.replace("www.", "")
                verify_tls = base_domain not in self.TLS_BYPASS_DOMAINS
                self.sessions[key] = requests.AsyncSession(
                    timeout=15.0,
                    allow_redirects=True,
                    impersonate=fingerprint["impersonate"],
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    verify=verify_tls,
                    http_version=2,
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

# ------------------------------------------------------------------------
# Layer 6.5: Proactive Domain Strategy Routing
# ------------------------------------------------------------------------
class TransportMode(str, Enum):
    CURL_FETCH_REPLAY = "curl_fetch_replay"
    DIRECT_API = "direct_api"
    BROWSER_REPLAY_REQUIRED = "browser_replay_required"


@dataclass(frozen=True)
class SiteStrategy:
    name: str
    domains: Tuple[str, ...]
    preferred_network: ProxyNetwork = ProxyNetwork.RESIDENTIAL
    expected_waf: ProxyClass = ProxyClass.GENERIC
    transport: TransportMode = TransportMode.CURL_FETCH_REPLAY
    api_first: bool = False
    allow_generic_api_guess: bool = False
    endpoint_templates: Tuple[str, ...] = ()
    id_path_patterns: Tuple[re.Pattern, ...] = ()
    needs_cookie_continuity: bool = True
    notes: str = ""


class StrategyRouter:
    DEFAULT = SiteStrategy(
        name="default",
        domains=(),
        preferred_network=ProxyNetwork.RESIDENTIAL,
        allow_generic_api_guess=True,
        id_path_patterns=(re.compile(r"/(?:products?|goods|product|item|shop-goods)/(\d{4,})"),),
    )
    PROFILES: Tuple[SiteStrategy, ...] = (
        SiteStrategy(
            name="musinsa",
            domains=("musinsa.com",),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            expected_waf=ProxyClass.AKAMAI,
            api_first=True,
            endpoint_templates=("/api2/goods/{product_id}", "/app/goods/{product_id}/0"),
            id_path_patterns=(re.compile(r"/(?:products?|goods)/(\d{4,})"),),
        ),
        SiteStrategy(
            name="29cm",
            domains=("29cm.co.kr",),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            api_first=True,
            endpoint_templates=("/api/products/{product_id}", "/api/v4/products/{product_id}"),
            id_path_patterns=(re.compile(r"/(?:products?|goods)/(\d{4,})"),),
        ),
        SiteStrategy(
            name="zara",
            domains=("zara.com",),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            api_first=True,
            endpoint_templates=("/itxrest/1/catalog/store/11719/category/0/product/{product_id}/detail",),
            id_path_patterns=(re.compile(r"-p(\d+)\.html"), re.compile(r"/(\d{5,})(?:[/?#]|$)")),
        ),
        SiteStrategy(
            name="hm",
            domains=("hm.com",),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            api_first=True,
            endpoint_templates=("/hmwebservices/service/product/ko_KR/{product_id}",),
            id_path_patterns=(re.compile(r"productpage\.(\d+)\.html"), re.compile(r"/(\d{5,})(?:[/?#]|$)")),
        ),
        SiteStrategy(
            name="ably",
            domains=("a-bly.com", "ably.team"),
            preferred_network=ProxyNetwork.MOBILE,
            expected_waf=ProxyClass.DATADOME,
            api_first=True,
            endpoint_templates=("/api/v2/goods/{product_id}", "/api/products/{product_id}"),
            id_path_patterns=(re.compile(r"/(?:goods|products)/(\d{4,})"),),
            notes="Mobile/residential identity is more important than latency for Ably.",
        ),
        SiteStrategy(
            name="kream",
            domains=("kream.co.kr",),
            preferred_network=ProxyNetwork.MOBILE,
            expected_waf=ProxyClass.KASADA,
            transport=TransportMode.BROWSER_REPLAY_REQUIRED,
            api_first=True,
            endpoint_templates=("/api/p/products/{product_id}", "/api/products/{product_id}", "/api/p/products/{product_id}/details"),
            id_path_patterns=(re.compile(r"/products/(\d{4,})"),),
            notes="Many product pages ship sparse HTML; use reverse-engineered API or a Camoufox/Patchright/Nodriver worker when API replay fails.",
        ),
        SiteStrategy(
            name="wconcept",
            domains=("wconcept.co.kr",),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            expected_waf=ProxyClass.AKAMAI,
            api_first=True,
            endpoint_templates=("/api/product/v1/products/{product_id}", "/api/products/{product_id}"),
            id_path_patterns=(re.compile(r"/(?:Product|products?)/(\d{4,})", re.IGNORECASE),),
        ),
        SiteStrategy(
            name="bunjang",
            domains=("bunjang.co.kr", "bjn.co.kr"),
            preferred_network=ProxyNetwork.RESIDENTIAL,
            api_first=True,
            endpoint_templates=("/api/1/product/{product_id}/detail_info.json",),
            id_path_patterns=(re.compile(r"/products/(\d{4,})"),),
        ),
    )

    @classmethod
    def for_url(cls, url: str) -> SiteStrategy:
        domain = urlparse(url).netloc.replace("www.", "")
        for profile in cls.PROFILES:
            if any(key in domain for key in profile.domains):
                return profile
        return cls.DEFAULT

# ------------------------------------------------------------------------
# Layer 7: WAF Detection & Strategy Routing
# ------------------------------------------------------------------------
@dataclass(frozen=True)
class WafDetection:
    waf: ProxyClass = ProxyClass.GENERIC
    confidence: float = 0.0
    signals: Tuple[str, ...] = ()


class WafDetector:
    SIGNATURES: Dict[ProxyClass, Tuple[str, ...]] = {
        ProxyClass.CLOUDFLARE: ("cf-browser-verification", "cf-chl-", "turnstile", "challenge-platform", "checking if the site connection is secure", "cloudflare"),
        ProxyClass.DATADOME: ("datadome", "dd_cookie", "dd-user-id", "datadome.co"),
        ProxyClass.PERIMETERX: ("px-captcha", "perimeterx", "_px3", "_pxvid"),
        ProxyClass.KASADA: ("kasada", "x-kpsdk", "kpsdk", "ips.js"),
        ProxyClass.AKAMAI: ("akamai", "akamai bot manager", "_abck", "bm_sz"),
        ProxyClass.IMPERVA: ("imperva", "incapsula", "visid_incap", "reese84"),
        ProxyClass.SHAPE: ("shape security", "shapesecurity", "_ssg", "f5-"),
    }
    BLOCK_STATUSES = {401, 403, 407, 409, 418, 429, 503}

    @classmethod
    def detect(cls, html: str, status: int = 200, headers: Optional[dict] = None) -> WafDetection:
        text = " ".join([html or "", " ".join(f"{k}={v}" for k, v in (headers or {}).items())]).lower()
        best = WafDetection()
        for waf, signatures in cls.SIGNATURES.items():
            hits = tuple(sig for sig in signatures if sig in text)
            if hits and len(hits) > len(best.signals):
                best = WafDetection(waf=waf, confidence=min(1.0, 0.35 + 0.2 * len(hits)), signals=hits)
        if best.confidence:
            return best
        if status in cls.BLOCK_STATUSES or (len(html or "") < 2000 and "window.location" in text):
            return WafDetection(waf=ProxyClass.GENERIC, confidence=0.4, signals=(f"status:{status}",))
        return best

    @classmethod
    def is_blocked(cls, html: str, status: int = 200, headers: Optional[dict] = None) -> bool:
        detection = cls.detect(html, status, headers)
        return detection.confidence >= 0.35


class AntiBotAnalyzer:
    @staticmethod
    def is_blocked(html: str, status: int = 200) -> bool:
        return WafDetector.is_blocked(html, status)

# ------------------------------------------------------------------------
# Layer 8: Base Extractors & JSON Helpers
# ------------------------------------------------------------------------
WHITESPACE_PATTERN = re.compile(r"\s+")
PRODUCT_ID_PATTERN = re.compile(r"(?:productNo|productId|goodsNo|goodsId|itemNo|itemId|styleId|sku)[\"'\s:=_-]+([A-Za-z0-9_-]{4,})", re.IGNORECASE)
PATH_ID_PATTERN = re.compile(r"/(?:products?|goods|product|item|shop-goods)/(\d{4,})")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return WHITESPACE_PATTERN.sub(" ", str(value)).strip()


def _json_loads(raw: str | bytes) -> Any:
    return orjson.loads(raw)


def _iter_dicts(value: Any) -> Iterable[dict]:
    queue = deque([value])
    while queue:
        current = queue.popleft()
        if isinstance(current, dict):
            yield current
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)


def _first_jmes(payload: Any, expressions: Iterable[str]) -> Any:
    for expression in expressions:
        value = jmespath.search(expression, payload)
        if value not in (None, "", [], {}):
            return value
    return None


def _get_node_text(node: Optional[Node]) -> str:
    if not node:
        return ""
    return node.text(strip=True) or ""


def _extract_script_json(tree: HTMLParser, selector: str) -> list[Any]:
    payloads = []
    for node in tree.css(selector):
        raw = node.text(strip=True)
        if not raw:
            continue
        try:
            payloads.append(_json_loads(re.sub(r"[\x00-\x1f]", "", raw)))
        except (orjson.JSONDecodeError, TypeError):
            continue
    return payloads


def _normalize_product_payload(payload: Any, base_url: str, source: str) -> dict:
    product = _first_jmes(payload, [
        "data.product", "data.goods", "data.item", "product", "goods", "item", "props.pageProps.product",
        "props.pageProps.goods", "props.pageProps.item", "props.pageProps.initialState.product",
        "pageProps.product", "pageProps.goods", "entities.product", "payload.product",
    ])
    if not isinstance(product, dict):
        product = next((candidate for candidate in _iter_dicts(payload) if _looks_like_product(candidate)), {})
    if not product:
        return {}

    title = _first_jmes(product, ["name", "title", "productName", "goodsName", "itemName", "displayName", "goodsNm"])
    price = _first_jmes(product, ["price", "salePrice", "normalPrice", "finalPrice", "discountedPrice", "goodsPrice", "sellPrice", "amount"])
    brand = _first_jmes(product, ["brand.name", "brandName", "brand", "maker", "manufacturer"])
    description = _first_jmes(product, ["description", "desc", "summary", "content", "shortDescription"])
    currency = _first_jmes(product, ["currency", "priceCurrency", "currencyCode"])
    availability = _first_jmes(product, ["availability", "stockStatus", "status", "saleStatus"])
    image_url = _first_jmes(product, [
        "image", "imageUrl", "thumbnail", "thumbnailUrl", "mainImage", "mainImageUrl", "images[0].url",
        "images[0]", "imageUrls[0]", "media[0].url", "photos[0].url",
    ])
    if isinstance(image_url, list):
        image_url = image_url[0] if image_url else ""
    if isinstance(brand, dict):
        brand = brand.get("name") or brand.get("brandName")

    return {
        "url": base_url,
        "title": _clean_text(title),
        "brand": _clean_text(brand),
        "price": _clean_text(price),
        "currency": _clean_text(currency) or "KRW",
        "availability": _clean_text(availability),
        "image_url": urljoin(base_url, _clean_text(image_url)) if image_url else "",
        "description": _clean_text(description),
        "source": source,
    }


def _looks_like_product(candidate: dict) -> bool:
    keys = {str(key).lower() for key in candidate.keys()}
    nameish = {"name", "title", "productname", "goodsname", "itemname", "displayname"}
    priceish = {"price", "saleprice", "normalprice", "finalprice", "discountedprice", "goodsprice"}
    imageish = {"image", "imageurl", "thumbnail", "thumbnailurl", "mainimage", "images", "imageurls"}
    return bool(keys & nameish) and (bool(keys & priceish) or bool(keys & imageish))

# ------------------------------------------------------------------------
# Layer 9: Product API Discovery / Site API Replay
# ------------------------------------------------------------------------
class ProductApiDiscoverer:
    GENERIC_ENDPOINTS = (
        "/api/products/{product_id}",
        "/api/product/{product_id}",
        "/api/goods/{product_id}",
        "/api2/goods/{product_id}",
        "/graphql",
    )

    async def discover_and_fetch(self, url: str, html: str, final_url: str, fp: dict, proxy: Optional[str], strategy: Optional[SiteStrategy] = None) -> dict:
        strategy = strategy or StrategyRouter.for_url(final_url)
        tree = HTMLParser(html) if html else None
        hydration_payloads = HydrationExtractor.extract_payloads(tree) if tree else []
        product_ids = self._extract_product_ids(url, html, hydration_payloads, strategy)
        return await self.fetch_from_strategy(final_url, fp, proxy, strategy, product_ids)

    async def fetch_from_strategy(self, url: str, fp: dict, proxy: Optional[str], strategy: SiteStrategy, product_ids: Optional[list[str]] = None) -> dict:
        product_ids = product_ids or self._extract_product_ids(url, "", [], strategy)
        if not product_ids:
            return {}

        endpoints = self._endpoint_templates(strategy)
        if not endpoints:
            return {}

        for product_id in product_ids[:5]:
            for template in endpoints:
                api_url = urljoin(url, template.format(product_id=product_id))
                payload = await self._fetch_json(api_url, url, fp, proxy, product_id)
                if not payload:
                    continue
                data = _normalize_product_payload(payload, url, f"site-api:{strategy.name}:{urlparse(api_url).path}")
                if QualityValidator.calculate_score(data) >= 0.65:
                    return data
        return {}

    def _extract_product_ids(self, url: str, html: str, payloads: list[Any], strategy: SiteStrategy) -> list[str]:
        ids = []
        parsed = urlparse(url)
        ids.extend(value for values in parse_qs(parsed.query).values() for value in values if value.isdigit())
        for pattern in strategy.id_path_patterns or (PATH_ID_PATTERN,):
            ids.extend(match.group(1) for match in pattern.finditer(parsed.path))
        for payload in payloads:
            for candidate in _iter_dicts(payload):
                for key in ("productNo", "productId", "goodsNo", "goodsId", "itemNo", "itemId", "styleId", "sku", "id"):
                    value = candidate.get(key)
                    if isinstance(value, (str, int)) and len(str(value)) >= 4:
                        ids.append(str(value))
        if html:
            ids.extend(match.group(1) for match in PRODUCT_ID_PATTERN.finditer(html[:200000]))
        return list(dict.fromkeys(ids))

    def _endpoint_templates(self, strategy: SiteStrategy) -> Tuple[str, ...]:
        # Known shopping domains should use maintained, reverse-engineered BFF/API
        # profiles. Blind generic probing is reserved for unknown domains only.
        if strategy.endpoint_templates:
            return strategy.endpoint_templates + (self.GENERIC_ENDPOINTS if strategy.allow_generic_api_guess else ())
        return self.GENERIC_ENDPOINTS if strategy.allow_generic_api_guess else ()

    async def _fetch_json(self, api_url: str, referer: str, fp: dict, proxy: Optional[str], product_id: str) -> Any:
        domain = urlparse(api_url).netloc
        client = await curl_pool.get_session(domain, fp, proxy)
        headers = _build_headers(fp, accept="application/json, text/plain, */*", referer=referer)
        if api_url.endswith("/graphql"):
            body = {
                "query": "query Product($id: ID!) { product(id: $id) { id name title price image imageUrl brand { name } description } }",
                "variables": {"id": product_id},
            }
            response = await client.post(api_url, headers={**headers, "content-type": "application/json"}, data=orjson.dumps(body))
        else:
            response = await client.get(api_url, headers=headers)
        if response.status_code >= 400 or not response.text:
            return None
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and not response.text.lstrip().startswith(("{", "[")):
            return None
        try:
            return _json_loads(response.content)
        except (orjson.JSONDecodeError, TypeError):
            return None

product_api_discoverer = ProductApiDiscoverer()

# ------------------------------------------------------------------------
# Layer 10: Deterministic Extractors
# ------------------------------------------------------------------------
class HydrationExtractor:
    SELECTORS = (
        'script#__NEXT_DATA__',
        'script#__NUXT_DATA__',
        'script[id="__NEXT_DATA__"]',
        'script[type="application/json"]',
    )
    JS_STATE_PATTERNS = (
        re.compile(r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;", re.DOTALL),
        re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;", re.DOTALL),
        re.compile(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*;", re.DOTALL),
        re.compile(r"window\.__RELAY_STORE__\s*=\s*(\{.*?\})\s*;", re.DOTALL),
    )

    @classmethod
    def extract_payloads(cls, tree: HTMLParser) -> list[Any]:
        payloads = []
        for selector in cls.SELECTORS:
            payloads.extend(_extract_script_json(tree, selector))
        for script in tree.css("script"):
            raw = script.text(strip=True)
            if not raw or "__" not in raw:
                continue
            for pattern in cls.JS_STATE_PATTERNS:
                match = pattern.search(raw)
                if match:
                    try:
                        payloads.append(_json_loads(match.group(1)))
                    except (orjson.JSONDecodeError, TypeError):
                        continue
        return payloads

    @classmethod
    def extract(cls, tree: HTMLParser, base_url: str) -> dict:
        for payload in cls.extract_payloads(tree):
            data = _normalize_product_payload(payload, base_url, "hydration-json")
            if QualityValidator.calculate_score(data) >= 0.55:
                return data
        return {}


class StructuredDataExtractor:
    @classmethod
    def extract(cls, tree: HTMLParser, base_url: str) -> dict:
        products = cls._json_ld_products(tree)
        product = products[0] if products else {}
        offers = product.get("offers", {}) if isinstance(product, dict) else {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        images = product.get("image", []) if isinstance(product, dict) else []
        if isinstance(images, str):
            images = [images]

        title_node = tree.css_first("title")
        data = {
            "url": base_url,
            "title": _clean_text(product.get("name") if isinstance(product, dict) else "") or cls._meta(tree, "og:title") or _get_node_text(title_node),
            "brand": _clean_text(product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else product.get("brand") if isinstance(product, dict) else ""),
            "price": _clean_text(offers.get("price") if isinstance(offers, dict) else "") or cls._meta(tree, "product:price:amount") or cls._meta(tree, "og:price:amount"),
            "currency": _clean_text(offers.get("priceCurrency") if isinstance(offers, dict) else "") or cls._meta(tree, "product:price:currency") or cls._meta(tree, "og:price:currency") or "KRW",
            "availability": _clean_text(offers.get("availability") if isinstance(offers, dict) else "").split("/")[-1],
            "image_url": "",
            "description": _clean_text(product.get("description") if isinstance(product, dict) else "") or cls._meta(tree, "og:description") or cls._meta(tree, "description"),
            "source": "structured-data",
        }
        image_url = _clean_text(images[0] if images else "") or cls._meta(tree, "og:image") or cls._meta(tree, "twitter:image") or cls._meta(tree, "image")
        if not image_url:
            for selector in ('img[id*="product"]', 'img[class*="product"]', ".product-image img"):
                img = tree.css_first(selector)
                if img and img.attributes.get("src"):
                    image_url = img.attributes["src"]
                    break
        data["image_url"] = urljoin(base_url, image_url) if image_url else ""
        return {k: v for k, v in data.items() if v or k in {"url", "source"}}

    @classmethod
    def _json_ld_products(cls, tree: HTMLParser) -> list[dict]:
        products = []
        for payload in _extract_script_json(tree, 'script[type="application/ld+json"]'):
            for candidate in payload if isinstance(payload, list) else [payload]:
                if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                    products.append(candidate)
                elif isinstance(candidate, dict) and isinstance(candidate.get("@graph"), list):
                    products.extend(item for item in candidate["@graph"] if isinstance(item, dict) and item.get("@type") == "Product")
        return products

    @staticmethod
    def _meta(tree: HTMLParser, property_name: str) -> str:
        selector = f'meta[property="{property_name}"], meta[name="{property_name}"], meta[itemprop="{property_name}"]'
        meta = tree.css_first(selector)
        return _clean_text(meta.attributes.get("content")) if meta else ""

# ------------------------------------------------------------------------
# Layer 11: Rule Engine & Quality Gate
# ------------------------------------------------------------------------
class RuleEngine:
    @staticmethod
    def apply(data: dict, final_url: str) -> dict:
        normalized = {**data}
        if normalized.get("image_url"):
            normalized["image_url"] = urljoin(final_url, normalized["image_url"])
        if "placeholder" in normalized.get("image_url", "").lower():
            normalized["image_url"] = ""
        if normalized.get("price"):
            normalized["price"] = _clean_text(normalized["price"])
        normalized.setdefault("currency", "KRW")
        normalized.setdefault("url", final_url)
        return normalized


class QualityValidator:
    @staticmethod
    def calculate_score(data: dict) -> float:
        score = 1.0
        if not data.get("title") or len(str(data["title"])) < 3:
            score -= 0.4
        if not data.get("price"):
            score -= 0.2
        if not data.get("image_url") or "placeholder" in str(data["image_url"]).lower():
            score -= 0.4
        return max(0.0, score)

# ------------------------------------------------------------------------
# Layer 12: Site-Specific Extractor Plugins
# ------------------------------------------------------------------------
class SiteExtractor:
    """도메인별 direct Product API 훅을 제공하는 베이스 클래스"""
    async def extract(self, url: str, html: str, tree: HTMLParser, data: dict, fp: dict, proxy: Optional[str]) -> dict:
        return data


class ApiFirstExtractor(SiteExtractor):
    async def extract(self, url: str, html: str, tree: HTMLParser, data: dict, fp: dict, proxy: Optional[str]) -> dict:
        strategy = StrategyRouter.for_url(url)
        api_data = await product_api_discoverer.discover_and_fetch(url, html, url, fp, proxy, strategy)
        return api_data or data


class MusinsaExtractor(ApiFirstExtractor): pass
class ZaraExtractor(ApiFirstExtractor): pass
class AblyExtractor(ApiFirstExtractor): pass
class HMExtractor(ApiFirstExtractor): pass
class TwentyNineCMExtractor(ApiFirstExtractor): pass
class KreamExtractor(ApiFirstExtractor): pass
class WConceptExtractor(ApiFirstExtractor): pass


class BunjangExtractor(ApiFirstExtractor):
    async def extract(self, url: str, html: str, tree: HTMLParser, data: dict, fp: dict, proxy: Optional[str]) -> dict:
        data = await super().extract(url, html, tree, data, fp, proxy)
        if "번개장터" in data.get("title", "") or data.get("title", "") == "취향을 잇는 거래":
            data["title"] = ""
        if "중고거래" in data.get("description", "") or "번개장터" in data.get("description", ""):
            data["description"] = ""
        img = data.get("image_url", "").lower()
        if "logo" in img or "bg_icon" in img:
            data["image_url"] = ""
        return data


EXTRACTOR_REGISTRY: Dict[str, Type[SiteExtractor]] = {
    "musinsa.com": MusinsaExtractor,
    "zara.com": ZaraExtractor,
    "a-bly.com": AblyExtractor,
    "ably.team": AblyExtractor,
    "hm.com": HMExtractor,
    "29cm.co.kr": TwentyNineCMExtractor,
    "kream.co.kr": KreamExtractor,
    "wconcept.co.kr": WConceptExtractor,
    "bunjang.co.kr": BunjangExtractor,
    "bjn.co.kr": BunjangExtractor,
}

# ------------------------------------------------------------------------
# Layer 13: Layered Retry & Network Pipeline
# ------------------------------------------------------------------------
def _build_headers(fp: dict, accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", referer: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "accept": accept,
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document" if "html" in accept else "empty",
        "sec-fetch-mode": "navigate" if "html" in accept else "cors",
        "sec-fetch-site": "none" if not referer else "same-origin",
        "upgrade-insecure-requests": "1",
        "user-agent": fp["user_agent"],
    }
    headers.update(fp.get("headers") or {})
    if referer:
        headers["referer"] = referer
    else:
        headers["referer"] = random.choice(["https://www.google.com/", "https://search.naver.com/", "https://www.bing.com/", "https://m.search.naver.com/"])
    return headers


async def _fetch_fast(url: str, proxy: Optional[str], fp: dict) -> Tuple[str, str, int, dict, float]:
    domain = urlparse(url).netloc
    client = await curl_pool.get_session(domain, fp, proxy)
    started_at = time.perf_counter()
    response = await client.get(url, headers=_build_headers(fp))
    latency_ms = (time.perf_counter() - started_at) * 1000
    return response.text, str(response.url), response.status_code, dict(response.headers), latency_ms


async def _execute_fetch_pipeline(url: str, strategy: Optional[SiteStrategy] = None) -> dict:
    """curl-cffi fetch replay with proactive site strategy and proxy-network routing."""
    strategy = strategy or StrategyRouter.for_url(url)
    fp = get_random_fingerprint()
    waf_class = strategy.expected_waf
    network = strategy.preferred_network
    proxy = await proxy_manager.get_proxy(waf_class, network)

    for attempt in range(3):
        try:
            html, final_url, status, headers, latency_ms = await _fetch_fast(url, proxy, fp)
            detection = WafDetector.detect(html, status, headers)
            if detection.confidence < 0.35:
                await proxy_manager.report(proxy, True, latency_ms, proxy_class=waf_class, network=network)
                metrics.success_total += 1
                return {"html": html, "finalUrl": final_url, "fingerprint": fp, "proxy": proxy}

            metrics.waf_blocks_total += 1
            waf_class = detection.waf
            await proxy_manager.report(proxy, False, latency_ms, blocked=True, proxy_class=waf_class, network=network)
            logger.warning("Fetch replay blocked; rerouting within preselected network pool", extra={"url": url, "site": strategy.name, "network": network.value, "waf": detection.waf.value, "signals": detection.signals})
            proxy = await proxy_manager.get_proxy(waf_class, network)
            fp = get_random_fingerprint()
        except Exception as exc:
            metrics.retries_total += 1
            await proxy_manager.report(proxy, False, proxy_class=waf_class, network=network)
            logger.warning("Fetch replay failed", extra={"url": url, "site": strategy.name, "network": network.value, "attempt": attempt + 1, "error": str(exc)})
            proxy = await proxy_manager.get_proxy(waf_class, network)
            fp = get_random_fingerprint()

    if strategy.transport == TransportMode.BROWSER_REPLAY_REQUIRED:
        raise AllTiersFailedError(f"{strategy.name} requires direct API replay or an external Camoufox/Patchright/Nodriver worker after curl replay failed: {url}")
    raise AllTiersFailedError(f"All fetch replay attempts exhausted for {url}")

# ------------------------------------------------------------------------
# Layer 14: Optional LLM Fallback Guardrail
# ------------------------------------------------------------------------
async def fallback_with_gemini(url: str, html_content: str):
    logger.warning("LLM fallback disabled by default; deterministic rule/API extraction did not meet quality gate", extra={"url": url, "html_hash": hashlib.sha256(html_content.encode("utf-8", errors="ignore")).hexdigest()})
    return None

# ------------------------------------------------------------------------
# Layer 15: Distributed-Ready Facade
# ------------------------------------------------------------------------
async def scrape_product_metadata(url: str) -> dict:
    metrics.requests_total += 1

    cached_result = await cache_manager.get(url)
    if cached_result:
        try:
            cached_result = json.loads(cached_result)
            metrics.success_total += 1
            return {**cached_result, "source": "cache"}
        except json.JSONDecodeError:
            pass

    async with rate_limiter.acquire(url):
        strategy = StrategyRouter.for_url(url)
        final_url = url
        html = ""
        fp = get_random_fingerprint()
        proxy = await proxy_manager.get_proxy(strategy.expected_waf, strategy.preferred_network)
        try:
            # Tier 0: known-domain API replay before fetching HTML. This avoids
            # sparse/empty SSR pages such as KREAM and reduces WAF exposure.
            if strategy.api_first:
                api_data = await product_api_discoverer.fetch_from_strategy(url, fp, proxy, strategy)
                if QualityValidator.calculate_score(api_data) >= 0.7:
                    metrics.api_discovery_total += 1
                    api_data = RuleEngine.apply(api_data, final_url)
                    await cache_manager.set(url, api_data)
                    return api_data

            page_data = await _execute_fetch_pipeline(url, strategy)
            html = page_data["html"]
            final_url = page_data["finalUrl"]
            fp = page_data["fingerprint"]
            proxy = page_data["proxy"]
            tree = HTMLParser(html)

            domain = urlparse(final_url).netloc.replace("www.", "")
            extractor_cls = next((ext for key, ext in EXTRACTOR_REGISTRY.items() if key in domain), SiteExtractor)

            # Tier 1: Site plugin / direct Product API discovery.
            extracted_data = await extractor_cls().extract(final_url, html, tree, {}, fp, proxy)
            if QualityValidator.calculate_score(extracted_data) >= 0.7:
                metrics.api_discovery_total += 1
                extracted_data = RuleEngine.apply(extracted_data, final_url)
                await cache_manager.set(url, extracted_data)
                return extracted_data

            # Tier 2: Hydration JSON extraction.
            hydration_data = HydrationExtractor.extract(tree, final_url)
            if QualityValidator.calculate_score(hydration_data) > QualityValidator.calculate_score(extracted_data):
                extracted_data = hydration_data
            if QualityValidator.calculate_score(extracted_data) >= 0.7:
                metrics.hydration_total += 1
                extracted_data = RuleEngine.apply(extracted_data, final_url)
                await cache_manager.set(url, extracted_data)
                return extracted_data

            # Tier 3: JSON-LD / OpenGraph / Twitter Card / Schema.org.
            structured_data = StructuredDataExtractor.extract(tree, final_url)
            if QualityValidator.calculate_score(structured_data) > QualityValidator.calculate_score(extracted_data):
                extracted_data = structured_data
            extracted_data = RuleEngine.apply(extracted_data, final_url)

            # Tier 4: LLM only for severely low quality after deterministic extraction.
            quality_score = QualityValidator.calculate_score(extracted_data)
            if quality_score < 0.3:
                if WafDetector.is_blocked(html):
                    raise BlockedError("WAF block detected")
                gemini_result = await fallback_with_gemini(final_url, html)
                if gemini_result and QualityValidator.calculate_score(gemini_result) >= 0.7:
                    metrics.fallback_llm_total += 1
                    await cache_manager.set(url, gemini_result)
                    return gemini_result

            metrics.structured_data_total += 1
            await cache_manager.set(url, extracted_data)
            return extracted_data
        except Exception as exc:
            logger.error("Extraction pipeline failed", extra={"url": url, "error": str(exc)})
            if html and len(html.strip()) > 100 and not WafDetector.is_blocked(html):
                gemini_result = await fallback_with_gemini(final_url, html)
                if gemini_result and QualityValidator.calculate_score(gemini_result) >= 0.7:
                    metrics.fallback_llm_total += 1
                    await cache_manager.set(url, gemini_result)
                    return gemini_result
            raise ValueError("Extraction failed.") from exc

# ------------------------------------------------------------------------
# Resource Cleanup Hooks (Call these on FastAPI lifespan shutdown)
# ------------------------------------------------------------------------
async def cleanup_crawler_resources():
    logger.info("Cleaning up crawler resources...")
    await curl_pool.close_all()
