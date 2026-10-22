"""One scraper path, such as ``r/python/new``, read from the page Reddit serves for it."""

from __future__ import annotations

import re
from typing import Any

from proprietary.reddit import fetch

from .cursor import next_cursor
from .document import parse
from .listing import listing, posts_listing
from .search import search_posts

_SEARCH = re.compile(r"(?:r/(?P<name>[^/]+)/)?search")
_COMMUNITY = re.compile(r"r/(?P<name>[^/]+)/(?P<sort>[a-z]+)")


async def read_listing(path: str, params: dict[str, Any] | None = None) -> Any | None:
    """The ``.json`` shape the scraper reads for ``path``, built from a logged-out page."""
    params = params or {}
    if match := _SEARCH.fullmatch(path):
        return await _search(match["name"], params)
    if match := _COMMUNITY.fullmatch(path):
        route = f"svc/shreddit/community-more-posts/{match['sort']}/"
        query = {
            "name": match["name"],
            "t": params.get("t"),
            "after": params.get("after"),
        }
        text = await fetch.fetch_page(route, _present(query))
        if text is None:
            return None
        page = parse(text)
        return posts_listing(page, next_cursor(page, route, "after"))
    return None


async def _search(name: str | None, params: dict[str, Any]) -> dict[str, Any] | None:
    route = f"svc/shreddit/r/{name}/search/" if name else "svc/shreddit/search/"
    query = {
        "q": params.get("q"),
        "type": "posts",
        "sort": params.get("sort"),
        "t": params.get("t"),
        "cursor": params.get("after"),
    }
    text = await fetch.fetch_page(route, _present(query))
    if text is None:
        return None
    page = parse(text)
    return listing(search_posts(page), next_cursor(page, route, "cursor"))


def _present(query: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in query.items() if value is not None}
