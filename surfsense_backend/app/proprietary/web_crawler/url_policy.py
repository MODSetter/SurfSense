# SurfSense proprietary crawler engine.
#
# Part of the ``app.proprietary`` package; licensed separately from the
# Apache-2.0 project root (see ``app/proprietary/LICENSE``).
"""URL helpers for the crawler: link extraction (connector) and host scope (spider).

Pure functions (no I/O). Dedupe/canonicalization and same-site link filtering now
live in Scrapling's ``Scheduler`` / ``LinkExtractor`` (see ``site_crawler``); only
these two primitives remain SurfSense-owned.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

from lxml import html as lxml_html
from lxml.etree import ParserError

from app.utils.crawl import is_social_host

_WHITESPACE_RE = re.compile(r"\s+")

# Anchor text cap: card-style links wrap whole article previews in one <a>;
# beyond this the text is a content dump, not a label.
_MAX_ANCHOR_TEXT = 200

# Context cap: nearest-ancestor text for icon-only anchors. Person/company
# cards ("Jane Doe General Partner") fit well under this; anything longer is
# a section dump and gets truncated rather than dropped.
_MAX_CONTEXT = 120


def _collapse(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _node_text(node: Any) -> str:
    # itertext + space-join keeps a word boundary between block elements,
    # where text_content() would glue "Jane Doe</h3><p>Partner" together.
    return _collapse(" ".join(node.itertext()))


def _anchor_label(anchor: Any) -> str:
    """Best label for an anchor: its text, else aria-label/title, else img alt."""
    text = _node_text(anchor)
    if text:
        return text
    for attr in ("aria-label", "title"):
        value = _collapse(anchor.get(attr) or "")
        if value:
            return value
    for alt in anchor.xpath(".//img/@alt"):
        value = _collapse(str(alt))
        if value:
            return value
    return ""


def _anchor_context(anchor: Any) -> str:
    """Nearest ancestor's text for unlabeled anchors (icon-only social links).

    Team/profile cards put the person's name next to — not inside — the icon
    link, so the closest ancestor with any text is the entity label we want.
    """
    node = anchor.getparent()
    while node is not None:
        text = _node_text(node)
        if text:
            return text[:_MAX_CONTEXT]
        node = node.getparent()
    return ""


def extract_link_records(page_html: str | None, base_url: str) -> list[dict[str, str]]:
    """Structured ``<a>`` inventory: ``{url, text, context, rel, kind}`` per target.

    ``kind`` is one of ``internal`` (same site as ``base_url``), ``external``,
    ``social`` (known profile host), ``email`` (``mailto:``), or ``tel``. http(s)
    targets are absolutized against ``base_url`` and fragment-stripped; the
    page's own URL is dropped. De-duplicated by target URL (first-seen order),
    keeping the first non-empty anchor text so a nav logo link doesn't shadow
    the labeled one.

    ``text`` falls back to aria-label/title/img-alt for icon-only anchors.
    ``context`` (social/email/tel only) is the nearest ancestor's text — team
    pages label a person *next to* their LinkedIn icon, not inside it, so this
    is what ties a profile URL to its entity.
    """
    if not page_html or not page_html.strip():
        return []
    try:
        root = lxml_html.fromstring(page_html)
    except (ParserError, ValueError):
        return []

    self_url, _ = urldefrag(base_url)
    base_host = host_of(base_url)
    records: dict[str, dict[str, str]] = {}

    for anchor in root.xpath("//a[@href]"):
        href = str(anchor.get("href", "")).strip()
        low = href.lower()
        # unquote: hrefs URL-encode spaces etc. ("tel:+1%20408-629-1770")
        if low.startswith("mailto:"):
            target = unquote(urlsplit(href).path.split("?")[0]).strip()
            kind = "email"
        elif low.startswith("tel:"):
            target = unquote(urlsplit(href).path).strip()
            kind = "tel"
        else:
            target, _ = urldefrag(urljoin(base_url, href))
            if urlsplit(target).scheme not in ("http", "https"):
                continue
            if target == self_url:
                continue
            host = (urlsplit(target).hostname or "").lower()
            if is_social_host(host):
                kind = "social"
            elif host_of(target) == base_host:
                kind = "internal"
            else:
                kind = "external"
        if not target:
            continue

        text = _anchor_label(anchor)[:_MAX_ANCHOR_TEXT]
        record = {
            "url": target,
            "text": text,
            "rel": str(anchor.get("rel", "")).strip(),
            "kind": kind,
        }
        # Context only where entity attribution matters; internal/external nav
        # context is boilerplate that would bloat every item.
        if kind in ("social", "email", "tel"):
            record["context"] = _anchor_context(anchor) if not text else ""
        existing = records.get(target)
        if existing is None:
            records[target] = record
        elif not existing["text"] and text:
            existing["text"] = text
            if "context" in existing:
                existing["context"] = ""
    return list(records.values())


def extract_links(page_html: str | None, base_url: str) -> list[str]:
    """Absolute, http(s), fragment-free, de-duplicated ``<a href>`` targets.

    URL-only view of ``extract_link_records`` for callers that just need the
    frontier; first-seen order is preserved to keep it stable.
    """
    return [
        record["url"]
        for record in extract_link_records(page_html, base_url)
        if record["kind"] not in ("email", "tel")
    ]


def host_of(url: str) -> str:
    """Lowercased host with a leading ``www.`` removed, for same-site matching."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host
