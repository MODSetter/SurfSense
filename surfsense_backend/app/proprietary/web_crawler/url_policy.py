# SurfSense proprietary crawler engine.
#
# Part of the ``app.proprietary`` package; licensed separately from the
# Apache-2.0 project root (see ``app/proprietary/LICENSE``).
"""URL helpers for the site crawler: link extraction, canonical key, same-site scope.

Pure functions (no I/O) so the crawl frontier stays deterministic and testable.
"""

from __future__ import annotations

from urllib.parse import urldefrag, urljoin, urlsplit

from lxml import html as lxml_html
from lxml.etree import ParserError
from w3lib.url import canonicalize_url as _w3lib_canonicalize_url


def extract_links(page_html: str | None, base_url: str) -> list[str]:
    """Absolute, http(s), fragment-free, de-duplicated ``<a href>`` targets.

    Relative hrefs resolve against ``base_url``; the page's own URL is dropped.
    First-seen order is preserved to keep the frontier stable.
    """
    if not page_html or not page_html.strip():
        return []
    try:
        root = lxml_html.fromstring(page_html)
    except (ParserError, ValueError):
        return []

    self_url, _ = urldefrag(base_url)
    seen: set[str] = set()
    links: list[str] = []
    for href in root.xpath("//a/@href"):
        target, _ = urldefrag(urljoin(base_url, href.strip()))
        if urlsplit(target).scheme not in ("http", "https"):
            continue
        if target == self_url or target in seen:
            continue
        seen.add(target)
        links.append(target)
    return links


def canonicalize_url(url: str) -> str:
    """Stable visited-set key: sorts query, normalizes encoding, drops fragment."""
    return _w3lib_canonicalize_url(url, keep_fragments=False)


def host_of(url: str) -> str:
    """Lowercased host with a leading ``www.`` removed, for same-site matching."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, allowed_hosts: set[str]) -> bool:
    """Whether ``url``'s host (``www.``-normalized) is in ``allowed_hosts``."""
    return host_of(url) in allowed_hosts
