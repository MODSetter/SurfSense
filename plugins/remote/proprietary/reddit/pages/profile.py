"""A user's profile feed: their posts and ``<shreddit-profile-comment>`` comments, in page order."""

from __future__ import annotations

import re
from typing import Any

from lxml import html

from .document import epoch, number, rich_text
from .listing import listing
from .posts import post_data

# A post in a subreddit, or on a user's own profile (their ``u_<name>`` subreddit).
_POST_PATH = re.compile(r"/(?P<kind>r|user)/(?P<sub>[^/]+)/comments/(?P<id>[^/]+)/")


def profile_listing(page: html.HtmlElement, after: str | None) -> dict[str, Any]:
    children = []
    for element in page.xpath("//shreddit-post | //shreddit-profile-comment"):
        if element.tag == "shreddit-post":
            children.append({"kind": "t3", "data": post_data(element)})
        else:
            children.append({"kind": "t1", "data": _comment_data(element)})
    return listing(children, after)


def _comment_data(element: html.HtmlElement) -> dict[str, Any]:
    fullname = element.get("comment-id") or ""
    rows = element.xpath(".//shreddit-comment-action-row")
    row = rows[0].attrib if rows else {}
    authors = element.xpath(f'.//*[@id="poster-info-{fullname}"]//a[1]')
    stamps = element.xpath(".//faceplate-timeago/@ts")
    bodies = element.xpath('.//*[contains(@id, "-post-rtjson-content")]')
    permalink = (row.get("permalink") or element.get("href") or "").split("?", 1)[0]
    post = _POST_PATH.match(permalink)
    subreddit = prefixed = None
    if post and post["kind"] == "r":
        subreddit, prefixed = post["sub"], f"r/{post['sub']}"
    elif post:
        subreddit, prefixed = f"u_{post['sub']}", f"u/{post['sub']}"
    return {
        "name": fullname,
        "id": fullname.split("_", 1)[1] if "_" in fullname else None,
        "permalink": permalink or None,
        "author": authors[0].text_content().strip() if authors else None,
        "body": rich_text(bodies[0]) if bodies else None,
        "score": number(row.get("score")),
        "subreddit": subreddit,
        "subreddit_name_prefixed": prefixed,
        "link_id": f"t3_{post['id']}" if post else None,
        "created_utc": epoch(stamps[0]) if stamps else None,
    }
