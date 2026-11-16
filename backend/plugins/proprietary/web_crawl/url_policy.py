"""A page's links with their anchor text and kind, and the host a crawl stays on."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html
from lxml.etree import ParserError

from proprietary.web_crawl.contacts import is_social_url

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


# When a page has more links than the cap, the site's own pages are kept
# first, then profile, email and phone links (they carry the entity labels),
# then everything else. A release-notes page links hundreds of contributor
# profiles, which would otherwise crowd out the site's pages.
_KIND_PRIORITY = {"internal": 0, "social": 1, "email": 1, "tel": 1, "external": 2}


def _tree(page: Any) -> Any:
    """``page`` parsed, or as-is when the caller already parsed it."""
    if not isinstance(page, str):
        return page
    if not page.strip():
        return None
    try:
        return lxml_html.fromstring(page)
    except (ParserError, ValueError):
        return None


def _join_base(root: Any, page_url: str) -> str:
    """What relative hrefs resolve against: ``<base href>`` when the page sets one."""
    for href in root.xpath("//base/@href")[:1]:
        href = str(href).strip()
        if href:
            return urljoin(page_url, href)
    return page_url


def _target(
    href: str, join_base: str, self_url: str, base_host: str
) -> tuple[str, str]:
    """``(target, kind)`` for one href; an empty target means skip it."""
    low = href.lower()
    # unquote: hrefs URL-encode spaces etc. ("tel:+1%20408-629-1770")
    if low.startswith("mailto:"):
        return unquote(urlsplit(href).path.split("?")[0]).strip(), "email"
    if low.startswith("tel:"):
        return unquote(urlsplit(href).path).strip(), "tel"
    target, _ = urldefrag(urljoin(join_base, href))
    if urlsplit(target).scheme not in ("http", "https") or target == self_url:
        return "", ""
    if is_social_url(target):
        return target, "social"
    if host_of(target) == base_host:
        return target, "internal"
    return target, "external"


def _record(target: str, kind: str, anchors: list[Any]) -> dict[str, str]:
    """One target's record: the first non-empty label among its anchors."""
    text = ""
    for anchor in anchors:
        text = _anchor_label(anchor)[:_MAX_ANCHOR_TEXT]
        if text:
            break
    record = {
        "url": target,
        "text": text,
        "rel": str(anchors[0].get("rel", "")).strip(),
        "kind": kind,
    }
    # Context only where entity attribution matters; internal/external nav
    # context is boilerplate that would bloat every item.
    if kind in ("social", "email", "tel"):
        record["context"] = "" if text else _anchor_context(anchors[0])
    return record


def link_inventory(
    page: Any, base_url: str, max_records: int | None = None
) -> tuple[list[dict[str, str]], int]:
    """``extract_link_records`` capped at ``max_records``, plus the uncapped count.

    ``page`` is HTML or an already parsed tree. Over the cap, records are kept
    by ``_KIND_PRIORITY`` and returned in page order; labels and context, the
    costly part, are computed only for the records kept.
    """
    root = _tree(page)
    if root is None:
        return [], 0

    self_url, _ = urldefrag(base_url)
    base_host = host_of(base_url)
    join_base = _join_base(root, base_url)
    found: dict[str, tuple[str, list[Any]]] = {}
    for anchor in root.xpath("//a[@href]"):
        target, kind = _target(
            str(anchor.get("href", "")).strip(), join_base, self_url, base_host
        )
        if not target:
            continue
        entry = found.get(target)
        if entry is None:
            found[target] = (kind, [anchor])
        else:
            entry[1].append(anchor)

    targets = list(found)
    total = len(targets)
    if max_records is not None and total > max_records:
        ranked = sorted(
            range(total), key=lambda i: _KIND_PRIORITY[found[targets[i]][0]]
        )
        targets = [targets[i] for i in sorted(ranked[:max_records])]
    return [_record(target, *found[target]) for target in targets], total


def extract_link_records(page_html: Any, base_url: str) -> list[dict[str, str]]:
    """Structured ``<a>`` inventory: ``{url, text, context, rel, kind}`` per target.

    ``kind`` is one of ``internal`` (same site as ``base_url``), ``external``,
    ``social`` (a profile on a known host), ``email`` (``mailto:``), or ``tel``.
    http(s) targets are absolutized against ``base_url`` (or the page's
    ``<base href>``) and fragment-stripped; the page's own URL is dropped.
    De-duplicated by target URL (first-seen order), keeping the first non-empty
    anchor text so a nav logo link doesn't shadow the labeled one.

    ``text`` falls back to aria-label/title/img-alt for icon-only anchors.
    ``context`` (social/email/tel only) is the nearest ancestor's text — team
    pages label a person *next to* their LinkedIn icon, not inside it, so this
    is what ties a profile URL to its entity.
    """
    return link_inventory(page_html, base_url)[0]


def extract_links(page_html: Any, base_url: str) -> list[str]:
    """Absolute, http(s), fragment-free, de-duplicated ``<a href>`` targets.

    The crawl frontier: no labels, so it stays cheap over a whole large page.
    First-seen order is preserved to keep it stable.
    """
    root = _tree(page_html)
    if root is None:
        return []
    self_url, _ = urldefrag(base_url)
    join_base = _join_base(root, base_url)
    links: dict[str, None] = {}
    # A changelog has 30,000 hrefs: skip repeats and in-page anchors before
    # the per-href URL work, which is most of the cost.
    in_page = join_base == base_url
    seen: set[str] = set()
    for raw in root.xpath("//a/@href"):
        href = str(raw).strip()
        if href in seen or (in_page and href.startswith("#")):
            continue
        seen.add(href)
        target, _ = urldefrag(urljoin(join_base, href))
        if urlsplit(target).scheme in ("http", "https") and target != self_url:
            links.setdefault(target)
    return list(links)


def host_of(url: str) -> str:
    """Lowercased host with a leading ``www.`` removed, for same-site matching."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def canonical_url(url: str) -> str:
    """``url`` as a crawl visits it: no fragment, lowercased scheme and host, ``/`` for no path."""
    parts = urlsplit(urldefrag(url)[0])
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )
