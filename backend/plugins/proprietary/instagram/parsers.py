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

import html
import json
import re
from datetime import UTC, datetime
from typing import Any

_BASE = "https://www.instagram.com"
_HASHTAG_RE = re.compile(r"#(\w+)")
# Instagram handles are letters/digits/period/underscore but never start or end
# with a period, so anchor both ends to alphanumerics/underscore — otherwise
# trailing sentence punctuation ("@hulu.") leaks into the handle.
_MENTION_RE = re.compile(r"@([A-Za-z0-9_](?:[A-Za-z0-9_.]*[A-Za-z0-9_])?)")
_TYPE_MAP = {
    "GraphImage": "Image",
    "GraphVideo": "Video",
    "GraphSidecar": "Sidecar",
    "XDTGraphImage": "Image",
    "XDTGraphVideo": "Video",
    "XDTGraphSidecar": "Sidecar",
}
# Mobile v1 ``media_type``: 1 = image, 2 = video, 8 = carousel/sidecar. Used by
# the single-post relay parser (the embedded PolarisMedia blob uses this int, not
# the GraphQL ``__typename`` the profile feed uses).
_MEDIA_TYPE = {1: "Image", 2: "Video", 8: "Sidecar"}


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


def _user_ref(user: Any) -> dict[str, Any] | None:
    """A trimmed public-user dict (tagged users / coauthor producers), or None.

    Normalizes the two anonymous dialects: the profile feed nests the handle
    under ``edge_media_to_tagged_user...node.user`` / ``coauthor_producers`` while
    the single-post relay blob uses ``usertags.in[].user`` — both carry the same
    scalar user fields, so this trims them to one shape.
    """
    if not isinstance(user, dict):
        return None
    ref = {
        "username": user.get("username"),
        "fullName": user.get("full_name"),
        "id": user.get("id") or user.get("pk"),
        "isVerified": user.get("is_verified"),
        "profilePicUrl": user.get("profile_pic_url"),
    }
    return ref if ref["username"] or ref["id"] else None


def _iv2_url(iv2: Any) -> str | None:
    """First candidate URL from a mobile ``image_versions2`` container, or None."""
    if isinstance(iv2, dict):
        cands = iv2.get("candidates")
        if isinstance(cands, list) and cands and isinstance(cands[0], dict):
            url = cands[0].get("url")
            return url if isinstance(url, str) else None
    return None


def _location_ref(loc: Any) -> tuple[str | None, str | None]:
    """``(name, id)`` from a location node, or ``(None, None)``."""
    if isinstance(loc, dict):
        lid = loc.get("id") or loc.get("pk")
        return loc.get("name"), (str(lid) if lid is not None else None)
    return None, None


def _feed_child(node: dict[str, Any]) -> dict[str, Any]:
    """Map a profile-feed ``edge_sidecar_to_children`` child to a childPost dict."""
    dims = node.get("dimensions") if isinstance(node.get("dimensions"), dict) else {}
    is_video = bool(node.get("is_video"))
    return {
        "id": node.get("id"),
        "shortCode": node.get("shortcode"),
        "type": "Video" if is_video else "Image",
        "displayUrl": node.get("display_url"),
        "videoUrl": node.get("video_url") if is_video else None,
        "alt": node.get("accessibility_caption"),
        "dimensionsHeight": _int(dims.get("height")),
        "dimensionsWidth": _int(dims.get("width")),
    }


def _relay_child(node: dict[str, Any]) -> dict[str, Any]:
    """Map a single-post relay ``carousel_media`` child to a childPost dict."""
    mt = node.get("media_type")
    vv = node.get("video_versions")
    video_url = (
        vv[0].get("url")
        if isinstance(vv, list) and vv and isinstance(vv[0], dict)
        else None
    )
    is_video = mt == 2 or bool(video_url)
    return {
        "id": node.get("id"),
        "shortCode": node.get("code"),
        "type": _MEDIA_TYPE.get(mt) or ("Video" if is_video else "Image"),
        "displayUrl": _iv2_url(node.get("image_versions2")) or node.get("display_uri"),
        "videoUrl": video_url,
        "alt": node.get("accessibility_caption"),
        "dimensionsHeight": _int(node.get("original_height")),
        "dimensionsWidth": _int(node.get("original_width")),
    }


def parse_media(node: dict[str, Any]) -> dict[str, Any]:
    """Map a raw timeline/feed media node to a flat media item dict."""
    code = _shortcode(node)
    caption = _caption_text(node)
    typename = node.get("__typename")
    owner = node.get("owner") if isinstance(node.get("owner"), dict) else {}
    dims = node.get("dimensions") if isinstance(node.get("dimensions"), dict) else {}
    is_video = bool(node.get("is_video"))
    children = _edges(node.get("edge_sidecar_to_children"))
    tagged = [
        ref
        for n in _edges(node.get("edge_media_to_tagged_user"))
        if (ref := _user_ref(n.get("user")))
    ]
    coauthors = [
        ref for c in (node.get("coauthor_producers") or []) if (ref := _user_ref(c))
    ]
    loc_name, loc_id = _location_ref(node.get("location"))
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
        "images": [c.get("display_url") for c in children if c.get("display_url")],
        "childPosts": [_feed_child(c) for c in children],
        "videoUrl": node.get("video_url") if is_video else None,
        "alt": node.get("accessibility_caption"),
        "likesCount": _likes_count(node),
        "videoViewCount": _int(node.get("video_view_count")) if is_video else None,
        "videoDuration": node.get("video_duration") if is_video else None,
        "timestamp": _utc_from_sec(node.get("taken_at_timestamp")),
        "ownerUsername": owner.get("username"),
        "ownerId": owner.get("id") or node.get("owner_id"),
        "ownerFullName": owner.get("full_name"),
        "isPinned": bool(node.get("pinned_for_users")),
        "productType": node.get("product_type"),
        "paidPartnership": node.get("is_paid_partnership"),
        "taggedUsers": tagged,
        "coauthorProducers": coauthors,
        "musicInfo": node.get("clips_music_attribution_info"),
        "locationName": loc_name,
        "locationId": loc_id,
        "isCommentsDisabled": node.get("comments_disabled"),
    }


def parse_profile(user: dict[str, Any]) -> dict[str, Any]:
    """Map a raw ``web_profile_info`` ``data.user`` to a flat profile item dict."""
    username = user.get("username")
    latest = [parse_media(n) for n in _edges(user.get("edge_owner_to_timeline_media"))]
    related = [
        ref for n in _edges(user.get("edge_related_profiles")) if (ref := _user_ref(n))
    ]
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
        "relatedProfiles": related,
        "latestPosts": latest,
    }


# Anonymous single-post extraction (/p/<shortcode>/, /reel/<shortcode>/) --------
#
# Instagram serves logged-out visitors the post's full metadata inside the
# document itself, not via a JSON XHR (the ``?__a=1`` API 404s / login-walls for
# anonymous callers). Two anonymous surfaces carry it, in order of fidelity:
#   1. An inline ``<script type="application/json">`` block embedding the mobile
#      v1 ``PolarisMedia`` object (pk, taken_at, media_type, like/comment counts,
#      caption, carousel_media, usertags, coauthor_producers, location, ...). This
#      is the same shape the app's private API returns and is the real source.
#   2. Open Graph ``<meta property="og:*">`` — a lossy fallback (og:description
#      packs "N likes, M comments - author on DATE: caption"). Used only if the
#      relay blob is somehow absent (e.g. a layout change).
# Live logged-out probes show NO ld+json on these pages, so it isn't parsed.
# ponytail: pinned to these two surfaces — if the relay shape drifts, update
# ``_find_media``; the wiring in scraper._media_flow stays the same.

_APP_JSON_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)
_OG_RE = re.compile(r'<meta\s+property="og:([^"]+)"\s+content="([^"]*)"', re.IGNORECASE)
# og tags are the fallback source (used only when the relay blob is absent). They
# follow a fixed English shape because the fetch layer pins Accept-Language en-US:
#   og:description = "{likes} likes, {comments} comments - {username} on {Month D, YYYY}: "{caption}""
#   og:title       = "{fullName} on Instagram: "{caption}""
# Each field is matched independently and guarded so an unrecognised shape (hidden
# likes, a non-English locale that slipped the header, a format change) degrades
# to None rather than crashing or polluting the caption.
_OG_COUNTS_RE = re.compile(
    r"([\d.,]+)\s+likes?,\s*([\d.,]+)\s+comments?", re.IGNORECASE
)
# The username sits after the counts' " - " and before " on {date}:"; the date is
# anchored to the English "Month D, YYYY" so a caption containing " on " or ":"
# can't be mistaken for the prefix.
_OG_OWNER_DATE_RE = re.compile(
    r"-\s+([^-\n]+?)\s+on\s+([A-Z][a-z]+ \d{1,2}, \d{4}):", re.DOTALL
)
# og:title is the cleaner caption source (no counts/date prefix): the caption is
# everything after "<fullName> on Instagram: ".
_OG_TITLE_RE = re.compile(r"^(.+?)\s+on Instagram:\s*(.*)$", re.DOTALL)
# The numeric media id (pk) rides in the App Link deep-link meta tags
# (al:ios:url / al:android:url = "instagram://media?id=<pk>") on anonymous pages,
# even though the og:* tags omit it.
_MEDIA_ID_RE = re.compile(r"instagram://media\?id=(\d+)")


def _og_date_to_iso(value: str) -> str | None:
    """``"July 9, 2026"`` -> ``"2026-07-09"`` (date-only; og carries no time)."""
    try:
        return (
            datetime.strptime(value, "%B %d, %Y").replace(tzinfo=UTC).date().isoformat()
        )
    except ValueError:
        return None


def _clean_caption(raw: str) -> str | None:
    """HTML-unescape and unwrap the surrounding quotes off an og caption preview."""
    return html.unescape(raw).strip().strip('"').strip() or None


def _parse_og_meta(og: dict[str, str]) -> dict[str, Any]:
    """Lift post fields out of Instagram's Open Graph tags (see module notes above).

    Caption + full name come from ``og:title``; counts + username + date from
    ``og:description``. Every field is optional and independently guarded, so a
    shape we don't recognise yields a partial (or empty) dict instead of raising.
    """
    out: dict[str, Any] = {}
    desc = og.get("description", "")
    title = og.get("title", "")

    counts = _OG_COUNTS_RE.search(desc)
    if counts:
        out["likes"] = _html_int(counts.group(1))
        out["comments"] = _html_int(counts.group(2))

    owner_date = _OG_OWNER_DATE_RE.search(desc)
    if owner_date:
        out["ownerUsername"] = owner_date.group(1).strip().lstrip("@") or None
        out["timestamp"] = _og_date_to_iso(owner_date.group(2))

    tm = _OG_TITLE_RE.match(title)
    if tm:
        out["ownerFullName"] = tm.group(1).strip() or None
        out["caption"] = _clean_caption(tm.group(2))
    elif owner_date:
        # No usable og:title: fall back to the caption after og:description's
        # date prefix — still clean (the counts/username/date are stripped).
        out["caption"] = _clean_caption(desc[owner_date.end() :])
    return out


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


def _og_tags(html: str) -> dict[str, str]:
    """Map ``og:<key>`` -> content for the post document."""
    return {k.lower(): v for k, v in _OG_RE.findall(html)}


def _find_media(root: Any, shortcode: str | None) -> dict[str, Any] | None:
    """Depth-first search a JSON tree for the post's mobile-v1 media object.

    Matches on ``code == shortcode`` (so a carousel *child* or a related post
    can't be picked instead of the target) plus ``taken_at`` and an id, which
    together uniquely identify the top-level ``PolarisMedia`` node.
    """
    stack = [root]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if (
                cur.get("taken_at") is not None
                and ("pk" in cur or "id" in cur)
                and (shortcode is None or cur.get("code") == shortcode)
            ):
                return cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _relay_media(html: str, shortcode: str | None) -> dict[str, Any] | None:
    """Locate the embedded ``PolarisMedia`` object for this post, or ``None``.

    The logged-out media payload is inlined as one of ~40 ``application/json``
    script blocks. We only ``json.loads`` blocks that mention ``taken_at`` (and
    the shortcode when known) so a single post fetch doesn't parse every blob.
    """
    for raw in _APP_JSON_RE.findall(html):
        if "taken_at" not in raw:
            continue
        if shortcode and shortcode not in raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        media = _find_media(data, shortcode)
        if media is not None:
            return media
    return None


def _media_from_relay(
    media: dict[str, Any], *, url: str, shortcode: str | None
) -> dict[str, Any]:
    """Map an embedded mobile-v1 ``PolarisMedia`` object to a flat media item.

    Same output shape as :func:`parse_media` (so it flows through
    ``InstagramMediaItem`` unchanged), sourced from the relay dialect
    (``user``/``taken_at``/``usertags.in``/``carousel_media``/flat counts).
    """
    mt = media.get("media_type")
    cap = media.get("caption")
    caption = (
        cap.get("text")
        if isinstance(cap, dict)
        else (cap if isinstance(cap, str) else None)
    )
    carousel = media.get("carousel_media")
    carousel = (
        [c for c in carousel if isinstance(c, dict)]
        if isinstance(carousel, list)
        else []
    )
    vv = media.get("video_versions")
    video_url = (
        vv[0].get("url")
        if isinstance(vv, list) and vv and isinstance(vv[0], dict)
        else None
    )
    is_video = mt == 2 or bool(video_url)
    owner = media.get("user") if isinstance(media.get("user"), dict) else {}
    tagged = [
        ref
        for t in ((media.get("usertags") or {}).get("in") or [])
        if isinstance(t, dict) and (ref := _user_ref(t.get("user")))
    ]
    coauthors = [
        ref for c in (media.get("coauthor_producers") or []) if (ref := _user_ref(c))
    ]
    loc_name, loc_id = _location_ref(media.get("location"))
    # The relay ``id`` is ``POLARIS_<pk>``; strip the prefix so single-post ids
    # match the numeric pk that og-fallback + the al:ios meta also yield.
    ident = media.get("id")
    if isinstance(ident, str) and ident.startswith("POLARIS_"):
        ident = ident[len("POLARIS_") :]
    pk = media.get("pk")
    media_id = ident or (str(pk) if pk is not None else None)
    return {
        "id": media_id,
        "type": _MEDIA_TYPE.get(mt) or ("Video" if is_video else "Image"),
        "shortCode": media.get("code") or shortcode,
        "caption": caption,
        "hashtags": list(dict.fromkeys(_HASHTAG_RE.findall(caption)))
        if caption
        else [],
        "mentions": list(dict.fromkeys(_MENTION_RE.findall(caption)))
        if caption
        else [],
        "url": url,
        "commentsCount": _int(media.get("comment_count")),
        "dimensionsHeight": _int(media.get("original_height")),
        "dimensionsWidth": _int(media.get("original_width")),
        "displayUrl": _iv2_url(media.get("image_versions2"))
        or media.get("display_uri"),
        "images": [
            u
            for c in carousel
            if (u := _iv2_url(c.get("image_versions2")) or c.get("display_uri"))
        ],
        "childPosts": [_relay_child(c) for c in carousel],
        "videoUrl": video_url,
        "alt": media.get("accessibility_caption"),
        "likesCount": _int(media.get("like_count")),
        "videoViewCount": _int(media.get("view_count") or media.get("play_count"))
        if is_video
        else None,
        "videoDuration": media.get("video_duration") if is_video else None,
        "timestamp": _utc_from_sec(media.get("taken_at")),
        "ownerUsername": owner.get("username"),
        "ownerId": owner.get("id") or owner.get("pk"),
        "ownerFullName": owner.get("full_name"),
        "productType": media.get("product_type"),
        "taggedUsers": tagged,
        "coauthorProducers": coauthors,
        "locationName": loc_name,
        "locationId": loc_id,
    }


def parse_post(
    html: str | None, *, url: str, shortcode: str | None = None
) -> dict[str, Any] | None:
    """Map an anonymous ``/p/<code>/`` (or ``/reel/``) HTML page to a media dict.

    Prefers the embedded mobile-v1 ``PolarisMedia`` relay JSON (full fidelity),
    falling back to the lossy Open Graph meta tags only if that blob is absent.
    Returns a dict shaped like :func:`parse_media` (so it flows through
    ``InstagramMediaItem`` unchanged), or ``None`` when the document carries
    neither surface (e.g. a login interstitial slipped past the fetch-layer
    redirect check — the caller treats ``None`` as "nothing to emit", never a
    silent success).
    """
    if not isinstance(html, str) or not html.strip():
        return None

    media = _relay_media(html, shortcode)
    if media is not None:
        return _media_from_relay(media, url=url, shortcode=shortcode)

    # Fallback: no embedded relay blob -> Open Graph meta only.
    og = _og_tags(html)
    if not og:
        return None
    og_meta = _parse_og_meta(og)
    caption = og_meta.get("caption")
    video_url = og.get("video")
    is_video = bool(video_url) or og.get("type") == "video.other"
    id_match = _MEDIA_ID_RE.search(html)
    return {
        "id": id_match.group(1) if id_match else None,
        "type": "Video" if is_video else "Image",
        "shortCode": shortcode,
        "caption": caption,
        "hashtags": list(dict.fromkeys(_HASHTAG_RE.findall(caption)))
        if caption
        else [],
        "mentions": list(dict.fromkeys(_MENTION_RE.findall(caption)))
        if caption
        else [],
        "url": url,
        "commentsCount": og_meta.get("comments"),
        "displayUrl": og.get("image"),
        "videoUrl": video_url if is_video else None,
        "likesCount": og_meta.get("likes"),
        "timestamp": og_meta.get("timestamp"),
        "ownerUsername": og_meta.get("ownerUsername"),
        "ownerFullName": og_meta.get("ownerFullName"),
    }
