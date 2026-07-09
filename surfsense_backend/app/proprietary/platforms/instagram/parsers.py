"""Pure JSON -> item mapping for the Instagram scraper.

Framework-agnostic and I/O-free so it can be unit-tested against captured
fixtures. Every function takes a raw Instagram web-JSON node and returns a plain
dict shaped like the public actor spec — no network, no proxy, no ``scrapedAt``
stamp (the orchestrator adds provenance so these stay deterministic under
fixture tests).

Instagram's web JSON nests media under GraphQL-style ``edge_*`` containers
(``edge_media_to_caption``, ``edge_liked_by``, ...) with ``taken_at_timestamp``
epoch seconds. These parsers flatten that into the actor's camelCase item shape.
Fields the anonymous endpoints don't expose are left unset (``None``/``[]``) so
parity is additive.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

_BASE = "https://www.instagram.com"
_HASHTAG_RE = re.compile(r"#(\w+)")
_MENTION_RE = re.compile(r"@([\w.]+)")
_TYPE_MAP = {
    "GraphImage": "Image",
    "GraphVideo": "Video",
    "GraphSidecar": "Sidecar",
    "XDTGraphImage": "Image",
    "XDTGraphVideo": "Video",
    "XDTGraphSidecar": "Sidecar",
}


def _int(value: Any) -> int | None:
    """Coerce to int, or ``None`` (never coerces bools)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _utc_from_sec(value: Any) -> str | None:
    """Epoch seconds -> millisecond ISO string, or ``None``."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    dt = datetime.fromtimestamp(float(value), tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _edge_count(node: dict[str, Any], key: str) -> int | None:
    """``node[key].count`` for a GraphQL ``edge_*`` container."""
    container = node.get(key)
    if isinstance(container, dict):
        return _int(container.get("count"))
    return None


def _edges(container: Any) -> list[dict[str, Any]]:
    """``container.edges[].node`` list for a GraphQL ``edge_*`` container."""
    if not isinstance(container, dict):
        return []
    out = []
    for edge in container.get("edges") or []:
        node = edge.get("node") if isinstance(edge, dict) else None
        if not isinstance(node, dict):
            continue
        out.append(node)
    return out


def _caption_text(node: dict[str, Any]) -> str | None:
    """First caption edge's text (web feed) or a flat ``caption`` fallback."""
    edges = _edges(node.get("edge_media_to_caption"))
    if edges:
        text = edges[0].get("text")
        if isinstance(text, str):
            return text
    cap = node.get("caption")
    if isinstance(cap, dict):
        cap = cap.get("text")
    if isinstance(cap, str):
        return cap
    return None


def _likes_count(node: dict[str, Any]) -> int | None:
    """Like count. ``-1`` (creator hid it) is passed through, never coerced."""
    for key in ("edge_liked_by", "edge_media_preview_like"):
        count = _edge_count(node, key)
        if count is not None:
            return count
    return _int(node.get("like_count"))


def _shortcode(node: dict[str, Any]) -> str | None:
    code = node.get("shortcode") or node.get("code")
    if isinstance(code, str):
        return code
    return None


def parse_media(node: dict[str, Any]) -> dict[str, Any]:
    """Map a raw timeline/feed media node to a flat media item dict."""
    code = _shortcode(node)
    caption = _caption_text(node)
    typename = node.get("__typename")
    owner = node.get("owner") if isinstance(node.get("owner"), dict) else {}
    dims = node.get("dimensions") if isinstance(node.get("dimensions"), dict) else {}
    is_video = bool(node.get("is_video"))
    return {
        "id": node.get("id"),
        "type": _TYPE_MAP.get(typename) or ("Video" if is_video else "Image"),
        "shortCode": code,
        "caption": caption,
        "hashtags": _HASHTAG_RE.findall(caption) if caption else [],
        "mentions": _MENTION_RE.findall(caption) if caption else [],
        "url": f"{_BASE}/p/{code}/" if code else None,
        "commentsCount": _edge_count(node, "edge_media_to_comment")
        or _int(node.get("comment_count")),
        "dimensionsHeight": _int(dims.get("height")),
        "dimensionsWidth": _int(dims.get("width")),
        "displayUrl": node.get("display_url"),
        "videoUrl": node.get("video_url") if is_video else None,
        "alt": node.get("accessibility_caption"),
        "likesCount": _likes_count(node),
        "videoViewCount": _int(node.get("video_view_count")) if is_video else None,
        "timestamp": _utc_from_sec(node.get("taken_at_timestamp")),
        "ownerUsername": owner.get("username"),
        "ownerId": owner.get("id") or node.get("owner_id"),
        "ownerFullName": owner.get("full_name"),
        "isCommentsDisabled": node.get("comments_disabled"),
    }


def parse_comment(node: dict[str, Any], *, post_url: str | None) -> dict[str, Any]:
    """Map a raw comment node to a flat comment item dict."""
    owner = node.get("owner") if isinstance(node.get("owner"), dict) else {}
    code = _shortcode(node)
    return {
        "id": node.get("id"),
        "postUrl": post_url,
        "commentUrl": f"{_BASE}/p/{code}/c/{node.get('id')}/" if code else None,
        "text": node.get("text"),
        "ownerUsername": owner.get("username"),
        "ownerProfilePicUrl": owner.get("profile_pic_url"),
        "timestamp": _utc_from_sec(node.get("created_at")),
        "repliesCount": _edge_count(node, "edge_threaded_comments")
        or _int(node.get("child_comment_count")),
        "likesCount": _edge_count(node, "edge_liked_by")
        or _int(node.get("comment_like_count")),
        "owner": {"id": owner.get("id"), "username": owner.get("username")}
        if owner
        else None,
    }


def parse_profile(user: dict[str, Any]) -> dict[str, Any]:
    """Map a raw ``web_profile_info`` ``data.user`` to a flat profile item dict."""
    username = user.get("username")
    latest = [parse_media(n) for n in _edges(user.get("edge_owner_to_timeline_media"))]
    return {
        "detailKind": "profile",
        "id": user.get("id"),
        "username": username,
        "url": f"{_BASE}/{username}/" if username else None,
        "fullName": user.get("full_name"),
        "biography": user.get("biography"),
        "externalUrl": user.get("external_url"),
        "followersCount": _edge_count(user, "edge_followed_by"),
        "followsCount": _edge_count(user, "edge_follow"),
        "postsCount": _edge_count(user, "edge_owner_to_timeline_media"),
        "highlightReelCount": _int(user.get("highlight_reel_count")),
        "igtvVideoCount": _edge_count(user, "edge_felix_video_timeline"),
        "isBusinessAccount": user.get("is_business_account"),
        "businessCategoryName": user.get("business_category_name"),
        "private": user.get("is_private"),
        "verified": user.get("is_verified"),
        "profilePicUrl": user.get("profile_pic_url"),
        "profilePicUrlHD": user.get("profile_pic_url_hd"),
        "latestPosts": latest,
    }


def parse_hashtag(data: dict[str, Any]) -> dict[str, Any]:
    """Map a raw ``tags/web_info`` payload to a flat hashtag item dict."""
    node = data.get("data") if isinstance(data.get("data"), dict) else data
    name = node.get("name")
    top = _edges(node.get("edge_hashtag_to_top_posts"))
    recent = _edges(node.get("edge_hashtag_to_media"))
    return {
        "detailKind": "hashtag",
        "id": node.get("id"),
        "name": name,
        "url": f"{_BASE}/explore/tags/{name}/" if name else None,
        "postsCount": _edge_count(node, "edge_hashtag_to_media"),
        "topPosts": [parse_media(n) for n in top],
        "posts": [parse_media(n) for n in recent],
    }


def parse_place(data: dict[str, Any]) -> dict[str, Any]:
    """Map a raw ``locations/web_info`` payload to a flat place item dict."""
    loc = data.get("location") if isinstance(data.get("location"), dict) else data
    recent = _edges(loc.get("edge_location_to_media"))
    return {
        "detailKind": "place",
        "name": loc.get("name"),
        "location_id": str(loc.get("id")) if loc.get("id") is not None else None,
        "slug": loc.get("slug"),
        "lat": loc.get("lat"),
        "lng": loc.get("lng"),
        "location_address": loc.get("address_json") or loc.get("address"),
        "location_city": loc.get("city"),
        "phone": loc.get("phone"),
        "website": loc.get("website"),
        "category": loc.get("category"),
        "media_count": _edge_count(loc, "edge_location_to_media"),
        "posts": [parse_media(n) for n in recent],
    }
