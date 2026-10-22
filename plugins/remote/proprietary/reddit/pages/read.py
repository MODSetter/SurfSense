"""One scraper path, such as ``r/python/new``, read from the page Reddit serves for it."""

from __future__ import annotations

import re
from typing import Any

from proprietary.reddit import fetch

from .comments import comment_tree, count
from .community import community_data
from .cursor import next_cursor
from .document import parse
from .listing import listing, posts_listing
from .more_comments import more_comments
from .posts import post_data
from .profile import profile_listing
from .search import search_posts

_POST = re.compile(r"(?:r/[^/]+/)?comments/(?P<id>[^/]+)")
_ABOUT = re.compile(r"r/(?P<name>[^/]+)/about")
_SEARCH = re.compile(r"(?:r/(?P<name>[^/]+)/)?search")
_USER = re.compile(r"user/(?P<name>[^/]+)(?:/(?P<tab>submitted|comments))?")
# Past the first, a post's comment batches each cost a request.
_MAX_COMMENT_BATCHES = 10
# A user's tab as the profile route that serves its feed.
_USER_FEEDS = {None: "overview", "submitted": "posts", "comments": "comments"}
_COMMUNITY = re.compile(r"r/(?P<name>[^/]+)/(?P<sort>[a-z]+)")


async def read_listing(path: str, params: dict[str, Any] | None = None) -> Any | None:
    """The ``.json`` shape the scraper reads for ``path``, built from a logged-out page."""
    params = params or {}
    if match := _POST.fullmatch(path):
        return await _post(match["id"], params.get("limit") or 0)
    if match := _ABOUT.fullmatch(path):
        return await _about(match["name"])
    if match := _USER.fullmatch(path):
        route = (
            f"svc/shreddit/profiles/profile_{_USER_FEEDS[match['tab']]}-more-posts/new/"
        )
        text = await fetch.fetch_page(
            route, _present({"name": match["name"], "after": params.get("after")})
        )
        if text is None:
            return None
        page = parse(text)
        return profile_listing(page, next_cursor(page, route, "after"))
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


async def _post(post_id: str, limit: int) -> list[dict[str, Any]] | None:
    """``[post Listing, comment Listing]``, the pair ``comments/<id>.json`` gave.

    Always ``comments/<id>``: ``r/<sub>/comments/<id>/`` without its slug serves
    an empty page (probe 2026-10-22).
    """
    text = await fetch.fetch_page(f"comments/{post_id}/")
    if text is None:
        return None
    page = parse(text)
    post = next(
        (
            post_data(element)
            for element in page.xpath("//shreddit-post")
            if element.get("id") == f"t3_{post_id}"
        ),
        None,
    )
    if post is None:
        return None
    batches = [page]
    while (
        len(batches) <= _MAX_COMMENT_BATCHES
        and count(comment_tree(batches, post)) < limit
        and (more := more_comments(batches[-1])) is not None
    ):
        text = await fetch.fetch_page(more.route, more.params, form=more.form)
        if text is None:
            break
        batches.append(parse(text))
    return [
        listing([{"kind": "t3", "data": post}]),
        listing(comment_tree(batches, post)),
    ]


async def _about(name: str) -> dict[str, Any] | None:
    """The subreddit's header from its top post's page.

    Its own pages, ``/r/<name>/`` and ``/about/``, often serve a JavaScript check
    instead (probe 2026-10-22); post pages and listings rarely do.
    """
    route = "svc/shreddit/community-more-posts/hot/"
    text = await fetch.fetch_page(route, {"name": name})
    if text is None:
        return None
    posts = parse(text).xpath("//shreddit-post")
    if not posts:
        return None
    over_18 = "subreddit-nsfw" in posts[0].attrib
    text = await fetch.fetch_page(f"comments/{posts[0].get('id', '')[3:]}/")
    headers = parse(text).xpath("//shreddit-subreddit-header") if text else []
    if not headers:
        return None
    return {"kind": "t5", "data": community_data(headers[0], over_18=over_18)}


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
