"""Where a listing page says its next page starts."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from lxml import html


def next_cursor(page: html.HtmlElement, route: str, param: str) -> str | None:
    """The ``param`` value of the partial that loads ``route``'s next page.

    A user's posts feed links none; its last post's ``more-posts-cursor`` is it.
    """
    for src in page.xpath("//faceplate-partial/@src"):
        parts = urlsplit(src)
        if parts.path.strip("/") != route.strip("/"):
            continue
        values = parse_qs(parts.query).get(param)
        if values:
            return values[0]
    cursors = page.xpath("//shreddit-post/@more-posts-cursor")
    return cursors[-1] if cursors else None
