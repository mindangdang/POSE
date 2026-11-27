from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpcore
import httpx
from bs4 import BeautifulSoup
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import AsyncNetworkBackend, AsyncNetworkStream

from project.backend.search_engine.schemas import SearchCandidate


MAX_BODY_BYTES = 1_000_000
MAX_REDIRECTS = 3
USER_AGENT = "POSESearchBot/2.0 (+public-page evidence fetch)"
NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")


def _is_public_destination(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if not address.is_global:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return address.ipv4_mapped.is_global
        if address in NAT64_WELL_KNOWN_PREFIX:
            embedded_ipv4 = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
            return embedded_ipv4.is_global
        # Do not let transition tunnels hide a private IPv4 destination.
        if address.sixtofour is not None or address.teredo is not None:
            return False
    return True


async def _resolved_public_addresses(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Private and local hosts are blocked")
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo, host, port, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise ValueError("Host could not be resolved") from exc
        addresses = list(dict.fromkeys(ipaddress.ip_address(record[4][0]) for record in records))
    if not addresses or any(not _is_public_destination(address) for address in addresses):
        raise ValueError("Private, loopback, and link-local addresses are blocked")
    return addresses


async def _validate_public_host(host: str) -> None:
    await _resolved_public_addresses(host, 443)


class PublicOnlyBackend(AsyncNetworkBackend):
    """Resolve and connect to a single validated IP, avoiding a second DNS lookup."""

    def __init__(self, backend: AsyncNetworkBackend | None = None) -> None:
        self.backend = backend or AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> AsyncNetworkStream:
        addresses = await _resolved_public_addresses(host, port)
        last_error: OSError | None = None
        for address in addresses:
            try:
                return await self.backend.connect_tcp(
                    host=str(address),
                    port=port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except OSError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ValueError("Host has no connectable public address")

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Any = None
    ) -> AsyncNetworkStream:
        raise ValueError("Unix domain sockets are not allowed for evidence retrieval")

    async def sleep(self, seconds: float) -> None:
        await self.backend.sleep(seconds)


class PublicOnlyHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self) -> None:
        super().__init__(trust_env=False, http1=True, http2=False, retries=0)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=8,
            max_keepalive_connections=4,
            keepalive_expiry=5.0,
            http1=True,
            http2=False,
            network_backend=PublicOnlyBackend(),
        )


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), "", "", ""))


async def _robots_allows(
    client: httpx.AsyncClient,
    url: str,
    cache: dict[str, RobotFileParser | None],
) -> bool:
    origin = _origin(url)
    if origin not in cache:
        parts = urlsplit(url)
        robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
        try:
            _, body, _ = await _checked_get(
                client,
                robots_url,
                {"text/plain", "text/html", "application/xhtml+xml"},
                check_robots=False,
            )
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
            cache[origin] = parser
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 404, 410}:
                cache[origin] = None
            else:
                raise
    policy: RobotFileParser | None = cache[origin]
    return policy is None or policy.can_fetch(USER_AGENT, url)


async def _checked_get(
    client: httpx.AsyncClient,
    url: str,
    allowed_types: set[str] | None = None,
    *,
    check_robots: bool = True,
    robots_cache: dict[str, RobotFileParser | None] | None = None,
) -> tuple[str, bytes, str]:
    current = url
    policy_cache = robots_cache if robots_cache is not None else {}
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            raise ValueError("Only absolute HTTP(S) URLs are allowed")
        await _validate_public_host(parts.hostname)
        if check_robots and not await _robots_allows(client, current, policy_cache):
            raise ValueError("Robots policy disallows evidence fetch")
        async with client.stream("GET", current, headers={"User-Agent": USER_AGENT}) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response has no destination")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            accepted_types = allowed_types or {"text/html", "application/xhtml+xml"}
            if content_type not in accepted_types:
                raise ValueError("Unexpected content type for evidence fetch")
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_BODY_BYTES:
                    raise ValueError("Response exceeds the evidence size limit")
                chunks.append(chunk)
            return str(response.url), b"".join(chunks), content_type
    raise ValueError("Too many redirects")


async def fetch_public_html(
    url: str,
    timeout_seconds: float = 6.0,
    *,
    client_factory: Callable[[httpx.Timeout], httpx.AsyncClient] | None = None,
) -> tuple[str, str]:
    """Fetch bounded public HTML and honor robots.txt at every redirect origin."""
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))
    factory = client_factory or (
        lambda request_timeout: httpx.AsyncClient(
            transport=PublicOnlyHTTPTransport(),
            timeout=request_timeout,
            follow_redirects=False,
            trust_env=False,
        )
    )
    async with factory(timeout) as client:
        robots_cache: dict[str, RobotFileParser | None] = {}
        final_url, payload, _ = await _checked_get(
            client, url, robots_cache=robots_cache
        )
    soup = BeautifulSoup(payload, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    text = " ".join(soup.stripped_strings)
    return final_url, text[:MAX_BODY_BYTES]


async def fetch_candidate_evidence(document: SearchCandidate) -> bool:
    try:
        final_url, content = await fetch_public_html(document.canonical_url)
        document.source_url = final_url
        document.content = content
        document.fetched_at = datetime.now(timezone.utc)
        return True
    except Exception:
        # A failed fetch leaves a snippet-only candidate with unknown evidence.
        return False
