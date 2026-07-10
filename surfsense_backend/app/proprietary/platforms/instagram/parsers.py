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

import json
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


# Anonymous single-post extraction (/p/<shortcode>/, /reel/<shortcode>/) --------
#
# Instagram serves logged-out visitors the post's public metadata inside the
# document itself, not via a JSON XHR (the ``?__a=1`` API 404s / login-walls for
# anonymous callers). Two durable, anonymous surfaces carry it:
#   1. ``<script type="application/ld+json">`` — schema.org VideoObject/ImageObject
#      with author, caption (articleBody/caption), uploadDate, interactionStatistic
#      (likes/comments), and the media URL.
#   2. Open Graph ``<meta property="og:*">`` — a lossy fallback (og:description
#      packs "N likes, M comments - author on DATE: caption").
# ld+json is preferred; og fills gaps. ponytail: pinned to these two surfaces —
# if a live probe shows a different embedded blob (e.g. a PolarisPost JSON), add a
# branch here; the wiring in scraper._media_flow stays the same.

_LDJSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_OG_RE = re.compile(
    r'<meta\s+property="og:([^"]+)"\s+content="([^"]*)"', re.IGNORECASE
)
# og:description shape: "1,234 likes, 56 comments - author on 2024-01-02 ..."
_OG_COUNTS_RE = re.compile(
    r"([\d.,]+)\s+likes?,\s*([\d.,]+)\s+comments?", re.IGNORECASE
)


def _html_int(value: Any) -> int | None:
    """Coerce a string/number (``"1,234"``) to int, or ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        digits = value.replace(",", "").strip()
        if digits.isdigit():
            return int(digits)
    return None


def _ldjson_blocks(html: str) -> list[dict[str, Any]]:
    """Parse every ``application/ld+json`` script block into dicts."""
    out: list[dict[str, Any]] = []
    for raw in _LDJSON_RE.findall(html):
        try:
            data = json.loads(raw.strip())
        except (ValueError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            if isinstance(node, dict):
                out.append(node)
    return out


def _og_tags(html: str) -> dict[str, str]:
    """Map ``og:<key>`` -> content for the post document."""
    return {k.lower(): v for k, v in _OG_RE.findall(html)}


def _ld_interaction(node: dict[str, Any]) -> dict[str, int]:
    """Pull like/comment counts out of schema.org ``interactionStatistic``."""
    stats = node.get("interactionStatistic")
    items = stats if isinstance(stats, list) else [stats] if stats else []
    out: dict[str, int] = {}
    for stat in items:
        if not isinstance(stat, dict):
            continue
        itype = str(stat.get("interactionType") or "")
        count = _html_int(stat.get("userInteractionCount"))
        if count is None:
            continue
        if "Like" in itype:
            out["likes"] = count
        elif "Comment" in itype:
            out["comments"] = count
    return out


def _ld_author_username(node: dict[str, Any]) -> str | None:
    """Owner handle from a schema.org ``author`` (alternateName / identifier)."""
    author = node.get("author")
    author = author[0] if isinstance(author, list) and author else author
    if not isinstance(author, dict):
        return None
    for key in ("alternateName", "identifier", "name"):
        val = author.get(key)
        if isinstance(val, dict):
            val = val.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip().lstrip("@") or None
    return None


def parse_post(html: str | None, *, url: str, shortcode: str | None = None) -> dict[str, Any] | None:
    """Map an anonymous ``/p/<code>/`` (or ``/reel/``) HTML page to a media dict.

    Prefers the embedded schema.org ``ld+json`` block, falling back to Open Graph
    meta tags for whatever it omits. Returns a dict shaped like
    :func:`parse_media` (so it flows through ``InstagramMediaItem`` unchanged), or
    ``None`` when the document carries neither surface (e.g. a login interstitial
    slipped past the fetch-layer redirect check — the caller treats ``None`` as
    "nothing to emit", never a silent success).
    """
    if not isinstance(html, str) or not html.strip():
        return None
    blocks = _ldjson_blocks(html)
    og = _og_tags(html)
    if not blocks and not og:
        return None

    node = next(
        (b for b in blocks if str(b.get("@type", "")).endswith(("Object", "Post"))),
        blocks[0] if blocks else {},
    )
    counts = _ld_interaction(node)
    if "likes" not in counts or "comments" not in counts:
        m = _OG_COUNTS_RE.search(og.get("description", ""))
        if m:
            counts.setdefault("likes", _html_int(m.group(1)) or 0)
            counts.setdefault("comments", _html_int(m.group(2)) or 0)

    caption = (
        node.get("articleBody")
        or node.get("caption")
        or node.get("description")
        or og.get("description")
    )
    caption = caption if isinstance(caption, str) else None

    video = node.get("video")
    video = video[0] if isinstance(video, list) and video else video
    video_url = (
        video.get("contentUrl") if isinstance(video, dict) else None
    ) or og.get("video")
    is_video = bool(video_url) or og.get("type") == "video.other"

    image = node.get("image")
    image = image[0] if isinstance(image, list) and image else image
    display_url = (
        image.get("url") if isinstance(image, dict) else image
        if isinstance(image, str)
        else None
    ) or og.get("image")

    return {
        "id": node.get("identifier") if isinstance(node.get("identifier"), str) else None,
        "type": "Video" if is_video else "Image",
        "shortCode": shortcode,
        "caption": caption,
        "hashtags": _HASHTAG_RE.findall(caption) if caption else [],
        "mentions": _MENTION_RE.findall(caption) if caption else [],
        "url": url,
        "commentsCount": counts.get("comments"),
        "displayUrl": display_url,
        "videoUrl": video_url if is_video else None,
        "likesCount": counts.get("likes"),
        "timestamp": node.get("uploadDate") or node.get("datePublished"),
        "ownerUsername": _ld_author_username(node),
    }
