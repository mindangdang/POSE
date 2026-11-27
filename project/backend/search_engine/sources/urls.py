from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_KEYS = {"gclid", "fbclid", "dclid", "mc_cid", "mc_eid"}


def canonicalize_url(url: str) -> str:
    """Normalize host and fragments while preserving meaningful query parameters."""
    parts = urlsplit(url.strip())
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("Only absolute HTTP(S) URLs can identify documents")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid URL port") from exc
    if port and port not in {80 if parts.scheme.lower() == "http" else 443}:
        host = f"{host}:{port}"
    if host.startswith("www."):
        host = host[4:]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def stable_document_id(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
