"""Classify a Google Maps URL and extract its identifier.

Covers the ``startUrls`` shapes the Apify specs accept: place pages
(``/maps/place``), search pages (``/maps/search``), review pages
(``/maps/reviews``), CID links (``google.com/maps?cid=***``), and short links
(``goo.gl/maps`` / ``maps.app.goo.gl``, which need a network redirect to
resolve — classified here, resolved later in the fetch layer).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

ResolvedKind = Literal["place", "search", "reviews", "cid", "shortlink"]

_MAPS_HOSTS = ("google.", "www.google.")
_SHORTLINK_HOSTS = ("goo.gl", "maps.app.goo.gl")

# Feature ID (a.k.a. "fid" / data_id): two hex halves, e.g.
# 0x89c3ca9c11f90c25:0x6cc8dba851799f09. It appears in the URL ``data=`` blob as
# ``!1s<hex:hex>`` and is the key that links a place to its detail/review RPCs.
_FID_RE = re.compile(r"(0x[0-9a-f]+:0x[0-9a-f]+)")


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    value: str  # place slug, search query, cid, or the short URL itself
    url: str
    fid: str | None = None  # feature id (hex:hex) when present in the URL


def extract_fid(url: str) -> str | None:
    """Pull the feature ID (``0x..:0x..``) out of a Google Maps URL, if present."""
    match = _FID_RE.search(url)
    return match.group(1) if match else None


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify a Google Maps URL into a scrape job, or ``None`` if unrecognized."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path or ""

    if hostname in _SHORTLINK_HOSTS or hostname.endswith(".goo.gl"):
        return ResolvedUrl("shortlink", url, url)

    if "google." not in hostname:
        return None

    # google.com/maps?cid=123... (uncommon but supported by both actors)
    cid = parse_qs(parsed.query).get("cid", [None])[0]
    if cid:
        return ResolvedUrl("cid", cid, url)

    for prefix, kind in (
        ("/maps/place/", "place"),
        ("/maps/search/", "search"),
        ("/maps/reviews/", "reviews"),
    ):
        if path.startswith(prefix):
            # Maps slugs encode spaces as "+" (e.g. /maps/place/Kim's+Island).
            value = unquote(path[len(prefix) :].split("/")[0].replace("+", " "))
            return ResolvedUrl(kind, value, url, extract_fid(url))  # type: ignore[arg-type]

    # Bare /maps/search or /maps/reviews carrying data in the query/data blob.
    for suffix, kind in (("/maps/search", "search"), ("/maps/reviews", "reviews")):
        if path.rstrip("/") == suffix:
            return ResolvedUrl(kind, url, url)  # type: ignore[arg-type]

    return None
