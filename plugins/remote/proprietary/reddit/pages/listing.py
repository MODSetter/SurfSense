"""A page of things as the ``.json`` Listing the scraper pages through."""

from __future__ import annotations

from typing import Any

from lxml import html

from .posts import post_data


def listing(children: list[dict[str, Any]], after: str | None = None) -> dict[str, Any]:
    return {"kind": "Listing", "data": {"children": children, "after": after}}


def posts_listing(page: html.HtmlElement, after: str | None) -> dict[str, Any]:
    return listing(
        [
            {"kind": "t3", "data": post_data(element)}
            for element in page.xpath("//shreddit-post")
        ],
        after,
    )
