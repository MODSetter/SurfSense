"""A search page's result units as the ``t3`` data ``search.json`` gave.

A unit carries its ids in a tracking attribute and its counts only in text. A
result with a preview of its text, most of them by relevance, has its own
wrapper around the same unit.
"""

from __future__ import annotations

import json
from typing import Any

from lxml import html

from .document import epoch, number


def search_posts(page: html.HtmlElement) -> list[dict[str, Any]]:
    return [
        {"kind": "t3", "data": data}
        for unit in page.xpath(
            '//*[@data-testid="search-post-unit"'
            ' or @data-testid="search-post-with-content-preview"]'
        )
        if (data := _post_data(unit)) is not None
    ]


def _post_data(unit: html.HtmlElement) -> dict[str, Any] | None:
    context = _tracking_context(unit)
    post = context.get("post") or {}
    fullname = post.get("id")
    if not isinstance(fullname, str) or "_" not in fullname:
        return None
    profile = context.get("profile") or {}
    subreddit = (context.get("subreddit") or {}).get("name")
    links = unit.xpath('.//a[@data-testid="post-title"]/@href')
    stamps = unit.xpath(".//faceplate-timeago/@ts")
    return {
        "name": fullname,
        "id": fullname.split("_", 1)[1],
        "permalink": links[0] if links else None,
        "title": post.get("title"),
        "author": profile.get("name"),
        "author_fullname": profile.get("id"),
        "subreddit": subreddit,
        "subreddit_name_prefixed": f"r/{subreddit}" if subreddit else None,
        "score": _count(unit, "vote"),
        "num_comments": _count(unit, "comment"),
        "over_18": post.get("nsfw") is True,
        "created_utc": epoch(stamps[0]) if stamps else None,
    }


def _tracking_context(unit: html.HtmlElement) -> dict[str, Any]:
    """The context of the unit's post link, whose ``type`` is ``post``."""
    for raw in unit.xpath(
        ".//search-telemetry-tracker/@data-faceplate-tracking-context"
    ):
        try:
            context = json.loads(raw)
        except ValueError:
            continue
        if (context.get("action_info") or {}).get("type") == "post":
            return context
    return {}


def _count(unit: html.HtmlElement, label: str) -> int | float | None:
    """The number before ``votes`` or ``comments`` in the unit's counter row."""
    for span in unit.xpath('.//*[@data-testid="search-counter-row"]/span'):
        numbers = span.xpath("./faceplate-number/@number")
        if numbers and label in span.text_content():
            return number(numbers[0])
    return None
