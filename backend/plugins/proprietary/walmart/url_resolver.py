"""Classify a Walmart start URL and extract its identifiers.

Covers the shapes accepted on input: product pages (``/ip/{slug}/{id}`` or
``/ip/{id}``), search (``/search?q=``), category (``/cp/{slug}/{id}``), and
browse (``/browse/...``) pages. Category and browse render the same
``searchResult`` JSON as search, so they share the ``listing`` kind and parser.

Pure, no I/O. ``item_id`` is Walmart's ``usItemId`` — the numeric id the review
page and detail page are both keyed on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

ResolvedKind = Literal["product", "listing"]

# usItemId: the trailing numeric segment of an /ip/ or /reviews/product/ path,
# or a bare numeric id passed directly.
_ITEM_ID_PATH_RE = re.compile(r"/(?:ip|reviews/product)/(?:[^/?#]+/)*(\d{4,})")
_BARE_ID_RE = re.compile(r"^\d{4,}$")

_LISTING_QUERY_KEYS = ("q", "cat_id", "browse")


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    url: str
    item_id: str | None = None
    domain: str | None = None


def extract_item_id(url: str) -> str | None:
    """Pull the numeric ``usItemId`` out of a product/review URL or bare id."""
    candidate = url.strip()
    if _BARE_ID_RE.match(candidate):
        return candidate
    match = _ITEM_ID_PATH_RE.search(candidate)
    return match.group(1) if match else None


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify a Walmart start URL into a scrape job, or ``None`` if unrecognized.

    A bare numeric id resolves to a product (its ``usItemId``) so callers can
    pass item ids directly without constructing a full URL.
    """
    if _BARE_ID_RE.match(url.strip()):
        return ResolvedUrl("product", url.strip(), item_id=url.strip())

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if "walmart." not in host:
        return None

    if path.startswith("/ip/"):
        return ResolvedUrl("product", url, item_id=extract_item_id(path), domain=host)

    query = parse_qs(parsed.query)
    is_listing = (
        path.startswith("/search")
        or path.startswith("/cp/")
        or path.startswith("/browse/")
        or any(key in query for key in _LISTING_QUERY_KEYS)
    )
    if is_listing:
        return ResolvedUrl("listing", url, domain=host)

    return None
