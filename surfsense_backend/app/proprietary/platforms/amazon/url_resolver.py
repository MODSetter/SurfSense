"""Classify an Amazon start URL and extract its identifiers.

Covers the ``categoryOrProductUrls`` shapes accepted on input: product
pages (``/dp/ASIN``, ``/gp/product/ASIN``), search / category pages (``/s?k=``,
``/s?bbn=``, ``/s?rh=``), bestsellers pages (``/zgbs/`` / ``/gp/bestsellers/``),
and shortened links (``a.co`` / ``amzn.to`` / ``amzn.eu``, which need a network
redirect to resolve — classified here, resolved later in the fetch layer).

Pure, no I/O. The ``marketplace`` suffix (``com``, ``de``, ``co.uk``, ...) is
derived from the host so the fetch layer can default the proxy country and UI
language without a separate geocoding step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

ResolvedKind = Literal["product", "search", "bestsellers", "shortened"]

_SHORTLINK_HOSTS = ("a.co", "amzn.to", "amzn.eu")

# ASIN: a 10-char uppercase alphanumeric id, carried in the canonical product
# path forms (``/dp/``, ``/gp/product/``, ``/product/``) or a ``?asin=`` query.
_ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product|product|d)/([A-Z0-9]{10})(?:[/?]|$)")
_ASIN_QUERY_RE = re.compile(r"[?&]asin=([A-Z0-9]{10})", re.IGNORECASE)

# Search/category pages carry their query in these params even without a /s path.
_SEARCH_QUERY_KEYS = ("k", "bbn", "rh")


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    url: str
    asin: str | None = None
    domain: str | None = None
    marketplace: str | None = None  # TLD suffix, e.g. "com", "de", "co.uk"


def extract_asin(url: str) -> str | None:
    """Pull the 10-char ASIN out of an Amazon product URL, if present."""
    match = _ASIN_PATH_RE.search(url)
    if match:
        return match.group(1)
    match = _ASIN_QUERY_RE.search(url)
    return match.group(1).upper() if match else None


def _marketplace_from_host(host: str) -> str | None:
    """The Amazon TLD suffix (``com``, ``de``, ``co.uk``, ...), or ``None``.

    Strips common subdomain prefixes and the ``amazon`` label, returning the
    remainder (e.g. ``www.amazon.co.jp`` -> ``co.jp``).
    """
    host = host.lower()
    for prefix in ("www.", "smile."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    if not host.startswith("amazon."):
        return None
    return host[len("amazon.") :] or None


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify an Amazon start URL into a scrape job, or ``None`` if unrecognized."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    # Shortened links resolve to their real URL later, in the fetch layer.
    if host in _SHORTLINK_HOSTS:
        return ResolvedUrl("shortened", url)

    if "amazon." not in host:
        return None

    marketplace = _marketplace_from_host(host)

    # Bestsellers before search: a /zgbs page has no /s path but is its own kind.
    if "/zgbs/" in path or path.startswith("/gp/bestsellers"):
        return ResolvedUrl("bestsellers", url, domain=host, marketplace=marketplace)

    # Product: canonical /dp/ (etc.) path with an ASIN.
    asin = extract_asin(url)
    if asin is not None:
        return ResolvedUrl(
            "product", url, asin=asin, domain=host, marketplace=marketplace
        )

    # Search / category: the /s path, or any search-carrying query param.
    query = parse_qs(parsed.query)
    if path.startswith("/s") or any(k in query for k in _SEARCH_QUERY_KEYS):
        return ResolvedUrl("search", url, domain=host, marketplace=marketplace)

    return None
