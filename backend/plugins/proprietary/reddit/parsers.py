"""Pure JSON -> item mapping for the Reddit scraper.

Framework-agnostic and I/O-free so it can be unit-tested against captured
fixtures. Every function takes raw Reddit ``.json`` data and returns plain
dicts / lists — no network, no proxy, no ``scrapedAt`` stamp (the orchestrator
adds the timestamp so these stay deterministic under fixture tests).

Reddit's ``.json`` wraps everything in "things" (``{"kind": "t3", "data":
{...}}``) and "Listings" (``{"kind": "Listing", "data": {"children": [...],
"after": ...}}``). ``t3`` = post, ``t1`` = comment, ``more`` = a truncated-reply
stub (out of scope v1 — treated as a branch stop).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_REDDIT_BASE = "https://www.reddit.com"


def _int(value: Any) -> int | None:
    """Coerce to int, or ``None`` (Reddit sometimes sends floats/None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _utc_from_sec(value: Any) -> str | None:
    """Epoch seconds -> millisecond ISO string, or ``None``."""
    if not isinstance(value, int | float):
        return None
    dt = datetime.fromtimestamp(float(value), tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO date (tolerating a trailing ``Z``) to aware UTC, else None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _before(created_utc: Any, date_limit: str | None) -> bool:
    """True if ``created_utc`` (epoch secs) predates the ISO ``date_limit``."""
    limit = _parse_iso(date_limit)
    if limit is None or not isinstance(created_utc, int | float):
        return False
    return datetime.fromtimestamp(float(created_utc), tz=UTC) < limit


def _thumbnail_url(value: Any) -> str | None:
    """Reddit uses sentinels like 'self'/'default'/'nsfw' for no thumbnail."""
    return value if isinstance(value, str) and value.startswith("http") else None


def _permalink_url(data: dict[str, Any]) -> str | None:
    permalink = data.get("permalink")
    return f"{_REDDIT_BASE}{permalink}" if isinstance(permalink, str) else None


def _strip_prefix(fullname: Any) -> str | None:
    """``t3_abc`` -> ``abc`` (Reddit fullname without its type prefix)."""
    if isinstance(fullname, str) and "_" in fullname:
        return fullname.split("_", 1)[1]
    return fullname if isinstance(fullname, str) else None


def _image_urls(data: dict[str, Any]) -> list[str]:
    """Best-effort image URLs from a post's ``preview.images[].source.url``."""
    preview = data.get("preview")
    if not isinstance(preview, dict):
        return []
    urls: list[str] = []
    for image in preview.get("images") or []:
        source = image.get("source") if isinstance(image, dict) else None
        url = source.get("url") if isinstance(source, dict) else None
        if isinstance(url, str) and url:
            urls.append(url)
    return urls


def _video_urls(data: dict[str, Any]) -> list[str]:
    """Best-effort video URL from ``media.reddit_video.fallback_url``."""
    for key in ("media", "secure_media"):
        media = data.get(key)
        if isinstance(media, dict):
            rv = media.get("reddit_video")
            url = rv.get("fallback_url") if isinstance(rv, dict) else None
            if isinstance(url, str) and url:
                return [url]
    return []


def children(listing: Any) -> list[dict[str, Any]]:
    """Return a Listing's ``data.children`` array (empty list if malformed)."""
    if isinstance(listing, dict):
        data = listing.get("data")
        if isinstance(data, dict):
            kids = data.get("children")
            if isinstance(kids, list):
                return kids
    return []


def after(listing: Any) -> str | None:
    """Return a Listing's ``data.after`` pagination cursor, or ``None``."""
    if isinstance(listing, dict):
        data = listing.get("data")
        if isinstance(data, dict):
            cursor = data.get("after")
            return cursor if isinstance(cursor, str) else None
    return None


def _unwrap(thing: dict[str, Any]) -> dict[str, Any]:
    """Accept a ``{"kind","data"}`` thing or a bare data dict; return the data."""
    data = thing.get("data")
    return data if isinstance(data, dict) else thing


def parse_post(thing: dict[str, Any]) -> dict[str, Any]:
    """Map a ``t3`` post thing (or its data dict) to a flat item dict."""
    data = _unwrap(thing)
    is_self = bool(data.get("is_self"))
    external = data.get("url") if not is_self else None
    return {
        "dataType": "post",
        "id": data.get("name"),
        "parsedId": data.get("id"),
        "url": _permalink_url(data),
        "username": data.get("author"),
        "userId": data.get("author_fullname"),
        "title": data.get("title"),
        "body": data.get("selftext") or None,
        "html": data.get("selftext_html"),
        "link": external,
        "externalUrl": external,
        "communityName": data.get("subreddit_name_prefixed"),
        "parsedCommunityName": data.get("subreddit"),
        "numberOfComments": _int(data.get("num_comments")),
        "upVotes": _int(data.get("score", data.get("ups"))),
        "upVoteRatio": data.get("upvote_ratio"),
        "over18": data.get("over_18"),
        "isVideo": data.get("is_video"),
        "flair": data.get("link_flair_text"),
        "authorFlair": data.get("author_flair_text"),
        "thumbnailUrl": _thumbnail_url(data.get("thumbnail")),
        "imageUrls": _image_urls(data),
        "videoUrls": _video_urls(data),
        "numberOfMembers": _int(data.get("subreddit_subscribers")),
        "createdAt": _utc_from_sec(data.get("created_utc")),
    }


def parse_community(thing: dict[str, Any]) -> dict[str, Any]:
    """Map a ``t5`` subreddit thing (``about.json``) to a flat community item."""
    data = _unwrap(thing)
    url = data.get("url")
    return {
        "dataType": "community",
        "id": data.get("name"),
        "parsedId": data.get("id"),
        "url": f"{_REDDIT_BASE}{url}" if isinstance(url, str) else None,
        "title": data.get("title"),
        "body": data.get("public_description") or None,
        "communityName": data.get("display_name_prefixed"),
        "parsedCommunityName": data.get("display_name"),
        "numberOfMembers": _int(data.get("subscribers")),
        "over18": data.get("over18"),
        "createdAt": _utc_from_sec(data.get("created_utc")),
    }


def parse_comment(thing: dict[str, Any], *, depth: int = 0) -> dict[str, Any]:
    """Map a ``t1`` comment thing (or its data dict) to a flat item dict.

    ``numberOfReplies`` is left at ``0`` here; :func:`flatten_comments` fills it
    with the count of descendant comments it actually emits.
    """
    data = _unwrap(thing)
    return {
        "dataType": "comment",
        "id": data.get("name"),
        "parsedId": data.get("id"),
        "url": _permalink_url(data),
        "username": data.get("author"),
        "userId": data.get("author_fullname"),
        "body": data.get("body") or None,
        "html": data.get("body_html"),
        "communityName": data.get("subreddit_name_prefixed"),
        "parsedCommunityName": data.get("subreddit"),
        "upVotes": _int(data.get("score", data.get("ups"))),
        "over18": data.get("over_18"),
        "authorFlair": data.get("author_flair_text"),
        "postId": _strip_prefix(data.get("link_id")),
        "parentId": data.get("parent_id"),
        "numberOfReplies": 0,
        "createdAt": _utc_from_sec(data.get("created_utc")),
        "depth": depth,
    }


def flatten_comments(
    comment_children: list[dict[str, Any]] | None,
    *,
    max_comments: int,
    date_limit: str | None = None,
    depth: int = 0,
    out: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Depth-first flatten a comment tree into a bounded flat list.

    Skips non-``t1`` children (``more`` stubs terminate that branch — v1),
    honors ``max_comments`` (total emitted, across all depths) and
    ``date_limit`` (drops comments older than the ISO cutoff). Each comment's
    ``numberOfReplies`` is set to the number of its descendants that were
    emitted.
    """
    if out is None:
        out = []
    for child in comment_children or []:
        if len(out) >= max_comments:
            break
        if not isinstance(child, dict) or child.get("kind") != "t1":
            continue  # 'more' stub / non-comment: stop this branch (v1)
        data = child.get("data") or {}
        if date_limit and _before(data.get("created_utc"), date_limit):
            continue
        item = parse_comment(data, depth=depth)
        before = len(out)
        out.append(item)
        replies = data.get("replies")
        flatten_comments(
            children(replies) if isinstance(replies, dict) else [],
            max_comments=max_comments,
            date_limit=date_limit,
            depth=depth + 1,
            out=out,
        )
        item["numberOfReplies"] = len(out) - before - 1
    return out
