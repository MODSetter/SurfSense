"""A ``<shreddit-post>`` as the ``t3`` data ``.json`` gave for the same post."""

from __future__ import annotations

from typing import Any

from lxml import html

from .document import epoch, number, rich_text

# Reddit's post-type for an uploaded image or video: its content-href is the media.
_IMAGE_TYPES = frozenset({"image", "gallery"})
_VIDEO_TYPES = frozenset({"video"})


def post_data(element: html.HtmlElement) -> dict[str, Any]:
    """The fields ``parsers.parse_post`` reads, from a post element's attributes."""
    attrs = element.attrib
    fullname = attrs.get("id") or ""
    domain = attrs.get("domain") or ""
    is_self = domain.startswith("self.")
    href = attrs.get("content-href")
    post_type = attrs.get("post-type") or ""
    bodies = element.xpath(f'.//*[@id="{fullname}-post-rtjson-content"]')
    flair = element.xpath(
        './/shreddit-post-flair//*[contains(@class, "flair-content")]'
    )
    data: dict[str, Any] = {
        "name": fullname or None,
        "id": fullname.split("_", 1)[1] if "_" in fullname else None,
        "permalink": attrs.get("permalink"),
        "title": attrs.get("post-title"),
        "author": attrs.get("author"),
        "author_fullname": attrs.get("author-id") or None,
        "selftext": rich_text(bodies[0]) if bodies else None,
        "is_self": is_self,
        "url": href,
        "subreddit": attrs.get("subreddit-name"),
        "subreddit_name_prefixed": attrs.get("subreddit-prefixed-name"),
        "num_comments": number(attrs.get("comment-count")),
        "score": number(attrs.get("score")),
        "upvote_ratio": number(attrs.get("upvote-ratio")),
        "over_18": "nsfw" in attrs,
        "is_video": post_type in _VIDEO_TYPES,
        "link_flair_text": flair[0].text_content().strip() if flair else None,
        "created_utc": epoch(attrs.get("created-timestamp")),
    }
    if post_type in _IMAGE_TYPES and href:
        data["preview"] = {"images": [{"source": {"url": href}}]}
    return data
