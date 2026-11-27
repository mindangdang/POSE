from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


MAX_BODY_BYTES = 1_000_000
MAX_REDIRECTS = 3
USER_AGENT = "POSESearchBot/2.0 (+public-page evidence fetch)"


async def _validate_public_host(host: str) -> None:
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Private and local hosts are blocked")
    try:
        ip = ipaddress.ip_address(host)
        addresses = [ip]
    except ValueError:
        records = await asyncio.to_thread(
            socket.getaddrinfo, host, None, type=socket.SOCK_STREAM
        )
        addresses = [ipaddress.ip_address(record[4][0]) for record in records]
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private, loopback, and link-local addresses are blocked")


async def _checked_get(
    client: httpx.AsyncClient,
    url: str,
    allowed_types: set[str] | None = None,
) -> tuple[str, bytes, str]:
    current = url
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
        async with client.stream("GET", current, headers={"User-Agent": USER_AGENT}) as response:
            if response.is_redirect:
                destination = urljoin(current, response.headers.get("location", ""))
                current = destination
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


async def fetch_public_html(url: str, timeout_seconds: float = 6.0) -> tuple[str, str]:
    """Fetch bounded public HTML and honor the origin's robots.txt policy."""
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        parts = urlsplit(url)
        if not parts.hostname:
            raise ValueError("Invalid URL")
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            _, robots, _ = await _checked_get(
                client,
                robots_url,
                {"text/plain", "text/html", "application/xhtml+xml"},
            )
            robots_text = robots.decode("utf-8", errors="replace")
            from urllib.robotparser import RobotFileParser

            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(robots_text.splitlines())
            if not parser.can_fetch(USER_AGENT, url):
                raise ValueError("Robots policy disallows evidence fetch")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {403, 404, 410}:
                raise
        final_url, payload, _ = await _checked_get(client, url)
    soup = BeautifulSoup(payload, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    text = " ".join(soup.stripped_strings)
    return final_url, text[:MAX_BODY_BYTES]
