"""Pure parsing/normalization for YouTube page + InnerTube JSON.

I/O-free and dependency-free (no ``jmespath``/``jsonpath-ng``): all traversal
uses two tiny helpers — :func:`find_all` (the ``$..key`` equivalent, same style
as ``_extract_playlist_video_ids`` in ``app/routes/youtube_routes.py``) and
:func:`dig` (null-safe positional get). Ported from the Scrapfly reference
``references/scrapfly-scrapers/youtube-scraper/youtube.py`` with all brittle deep
jmespath paths rewritten and the throwing ``convert_to_number`` replaced by a
robust :func:`parse_count`.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Traversal helpers
# ---------------------------------------------------------------------------


def find_all(obj: Any, key: str) -> list[Any]:
    """Collect every value stored under ``key`` anywhere in a nested structure."""
    out: list[Any] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key:
                    out.append(v)
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(obj)
    return out


def find_first(obj: Any, key: str) -> Any:
    """First value stored under ``key`` anywhere in the structure, else ``None``."""
    matches = find_all(obj, key)
    return matches[0] if matches else None


def find_last(obj: Any, key: str) -> Any:
    """Last value stored under ``key`` (continuation tokens want the newest)."""
    matches = find_all(obj, key)
    return matches[-1] if matches else None


def dig(obj: Any, *path: Any) -> Any:
    """Null-safe positional get through dict keys / list indices."""
    cur = obj
    for step in path:
        if isinstance(step, int) and isinstance(cur, list):
            if -len(cur) <= step < len(cur):
                cur = cur[step]
            else:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(step)
        else:
            return None
        if cur is None:
            return None
    return cur


# ---------------------------------------------------------------------------
# Value normalization
# ---------------------------------------------------------------------------

_COUNT_RE = re.compile(r"([\d,.]+)\s*([KMB]?)", re.IGNORECASE)
_MULTIPLIER = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_count(value: Any) -> int | None:
    """Normalize a YouTube count string to an int, else ``None``.

    Handles ``"451K views"``, ``"1.2M"``, ``"1,234"``, plain ints, and returns
    ``None`` for ``"No views"`` / missing (the reference's ``convert_to_number``
    throws on all of these).
    """
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    if not isinstance(value, str):
        return None
    match = _COUNT_RE.search(value.strip())
    if not match:
        return None
    number, suffix = match.group(1), match.group(2).upper()
    number = number.replace(",", "")
    if number in ("", "."):
        return None
    try:
        return int(float(number) * _MULTIPLIER[suffix])
    except (ValueError, KeyError):
        return None


def parse_date(microformat: dict | None) -> str | None:
    """Prefer the real publish date from a video's microformat renderer.

    ``playerMicroformatRenderer.publishDate`` is an actual date (``2024-08-27``),
    unlike the relative ``"7 days ago"`` strings on list pages.
    """
    if not microformat:
        return None
    return microformat.get("publishDate") or microformat.get("uploadDate")


def seconds_to_duration(seconds: Any) -> str | None:
    """Format a length in seconds as ``HH:MM:SS`` (Apify ``duration`` shape)."""
    total = parse_count(seconds)
    if total is None:
        return None
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _best_thumbnail(thumbnails: Any) -> str | None:
    """Return the highest-resolution thumbnail URL from a thumbnails list."""
    if not isinstance(thumbnails, list) or not thumbnails:
        return None
    best = None
    best_area = -1
    for t in thumbnails:
        if not isinstance(t, dict) or "url" not in t:
            continue
        area = (t.get("width") or 0) * (t.get("height") or 0)
        if area >= best_area:
            best_area = area
            best = t["url"]
    return best


# ---------------------------------------------------------------------------
# Embedded page-JSON extraction (brace matcher, from youtube_routes.py)
# ---------------------------------------------------------------------------


def _extract_json_object(html: str, patterns: list[re.Pattern[str]]) -> dict | None:
    start = -1
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            start = match.end()
            break
    if start == -1:
        return None

    depth = 0
    i = start
    while i < len(html):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        elif ch == '"':
            i += 1
            while i < len(html) and html[i] != '"':
                if html[i] == "\\":
                    i += 1
                i += 1
        i += 1

    try:
        return json.loads(html[start : i + 1])
    except (json.JSONDecodeError, IndexError):
        return None


def extract_yt_initial_data(html: str) -> dict | None:
    """Extract the ``ytInitialData`` object embedded in a YouTube page."""
    return _extract_json_object(
        html,
        [
            re.compile(r"var\s+ytInitialData\s*=\s*"),
            re.compile(r'window\["ytInitialData"\]\s*=\s*'),
        ],
    )


def extract_yt_initial_player_response(html: str) -> dict | None:
    """Extract the ``ytInitialPlayerResponse`` object from a video page."""
    return _extract_json_object(
        html,
        [
            re.compile(r"var\s+ytInitialPlayerResponse\s*=\s*"),
            re.compile(r'window\["ytInitialPlayerResponse"\]\s*=\s*'),
        ],
    )


# ---------------------------------------------------------------------------
# Page / API parsers -> partial VideoItem dicts
# ---------------------------------------------------------------------------


def _unwrap_redirect(url: str) -> str:
    """Resolve a ``youtube.com/redirect?...&q=<target>`` link to its target."""
    if "/redirect" in url and "q=" in url:
        q = parse_qs(urlparse(url).query).get("q")
        if q:
            return q[0]
    if url.startswith("/"):
        return f"https://www.youtube.com{url}"
    return url


def parse_description_links(initial: dict) -> list[dict[str, str]] | None:
    """Extract ``{url, text}`` links from the video's attributed description.

    Each ``commandRun`` marks a linked span (``startIndex``/``length``) into the
    description ``content``; external links are wrapped in a YouTube redirect
    whose real target is the ``q`` query param.
    """
    ad = find_first(initial, "attributedDescription")
    if not isinstance(ad, dict):
        return None
    content = ad.get("content") or ""
    # YouTube's startIndex/length are UTF-16 code-unit offsets (JS string
    # semantics); emoji in the description are surrogate pairs, so slice on the
    # UTF-16-LE bytes to keep spans aligned instead of Python code points.
    units = content.encode("utf-16-le")
    out: list[dict[str, str]] = []
    for run in ad.get("commandRuns") or []:
        start, length = run.get("startIndex"), run.get("length")
        if not isinstance(start, int) or not isinstance(length, int):
            continue
        cmd = dig(run, "onTap", "innertubeCommand")
        url = dig(cmd, "urlEndpoint", "url") or dig(
            cmd, "commandMetadata", "webCommandMetadata", "url"
        )
        if not url:
            continue
        text = units[start * 2 : (start + length) * 2].decode("utf-16-le", "ignore")
        out.append({"url": _unwrap_redirect(url), "text": text})
    return out or None


def _comments_turned_off(initial: dict) -> bool | None:
    """Detect a disabled comments section, else ``None`` if no section is present.

    An enabled section carries a ``continuationItemRenderer`` (the token that
    loads the comments); a disabled one keeps the section but drops the token.
    """
    sections = [
        s
        for s in find_all(initial, "itemSectionRenderer")
        if isinstance(s, dict) and s.get("sectionIdentifier") == "comment-item-section"
    ]
    if not sections:
        return None
    return not any(find_all(s, "continuationItemRenderer") for s in sections)


def _is_members_only(player: dict, initial: dict) -> bool:
    """True for members-only videos (a members badge or a members-only offer)."""
    for badge in find_all(initial, "metadataBadgeRenderer"):
        if (
            isinstance(badge, dict)
            and badge.get("style") == "BADGE_STYLE_TYPE_MEMBERS_ONLY"
        ):
            return True
    status = player.get("playabilityStatus") or {}
    return find_first(status, "offerId") == "sponsors_only_video"


def _is_age_restricted(player: dict, microformat: dict) -> bool | None:
    """True when the player response signals an age gate, else ``None``.

    ``playabilityStatus`` is authoritative (age-gated videos report a legacy age
    gate reason or an "age"-mentioning reason); ``isFamilySafe`` is the fallback.
    """
    status = player.get("playabilityStatus")
    if isinstance(status, dict):
        reason = (status.get("reason") or "").lower()
        if status.get("desktopLegacyAgeGateReason") or "age" in reason:
            return True
    if microformat.get("isFamilySafe") is False:
        return True
    return None


def _channel_from_byline(renderer: dict) -> dict[str, Any]:
    """Pull channel name/id/url from a list item's owner byline runs.

    Search ``videoRenderer``s carry the uploader in ``ownerText`` /
    ``longBylineText``; the run's ``browseEndpoint`` holds the channel id and the
    canonical ``/@handle`` (or ``/channel/UC...``) url.
    """
    run = dig(renderer, "ownerText", "runs", 0) or dig(
        renderer, "longBylineText", "runs", 0
    )
    if not isinstance(run, dict):
        return {}
    browse = dig(run, "navigationEndpoint", "browseEndpoint") or {}
    cid = browse.get("browseId")
    base = browse.get("canonicalBaseUrl")
    out: dict[str, Any] = {}
    if run.get("text"):
        out["channelName"] = run["text"]
    if cid:
        out["channelId"] = cid
    if isinstance(base, str) and base:
        out["channelUrl"] = f"https://www.youtube.com{base}"
        if base.startswith("/@"):
            out["channelUsername"] = base[2:] or None
    elif cid:
        out["channelUrl"] = f"https://www.youtube.com/channel/{cid}"
    return out


def parse_channel_metadata(initial_data: dict) -> dict[str, Any]:
    """Channel identity from ``channelMetadataRenderer`` (in the channel HTML).

    Zero extra fetch: name/id/url/avatar/description are already in the channel
    page's ``ytInitialData`` and apply to every video the channel flow yields.
    """
    meta = find_first(initial_data, "channelMetadataRenderer")
    if not isinstance(meta, dict):
        return {}
    out: dict[str, Any] = {}
    if meta.get("title"):
        out["channelName"] = meta["title"]
    if meta.get("externalId"):
        out["channelId"] = meta["externalId"]
    if meta.get("description"):
        out["channelDescription"] = meta["description"]
    url = meta.get("vanityChannelUrl") or meta.get("channelUrl")
    if url:
        out["channelUrl"] = url
    avatar = _best_thumbnail(dig(meta, "avatar", "thumbnails"))
    if avatar:
        out["channelAvatarUrl"] = avatar
    banner = _best_thumbnail(
        dig(
            find_first(initial_data, "pageHeaderViewModel"),
            "banner",
            "imageBannerViewModel",
            "image",
            "sources",
        )
    )
    if banner:
        out["channelBannerUrl"] = banner
    return out


def channel_about_tokens(initial_data: dict) -> list[str]:
    """Continuation tokens for the channel's engagement panels (one is About).

    The About panel isn't embedded in the channel HTML; it's fetched via a
    ``/browse`` continuation. Panels aren't labeled, so callers try each token
    and keep the response that yields an ``aboutChannelViewModel``.
    """
    tokens: list[str] = []
    for ep in find_all(initial_data, "showEngagementPanelEndpoint"):
        token = dig(find_first(ep, "continuationCommand"), "token")
        if token:
            tokens.append(token)
    return tokens


def parse_channel_about(about: dict) -> dict[str, Any]:
    """Deep channel fields from an ``aboutChannelViewModel``."""
    out: dict[str, Any] = {}
    if about.get("description"):
        out["channelDescription"] = about["description"]
    if about.get("country"):
        out["channelLocation"] = about["country"]
    subs = parse_count(about.get("subscriberCountText"))
    if subs is not None:
        out["numberOfSubscribers"] = subs
    views = parse_count(about.get("viewCountText"))
    if views is not None:
        out["channelTotalViews"] = views
    videos = parse_count(about.get("videoCountText"))
    if videos is not None:
        out["channelTotalVideos"] = videos
    joined = dig(about, "joinedDateText", "content") or about.get("joinedDateText")
    if isinstance(joined, str) and joined:
        # "Joined Feb 8, 2005" -> keep the date portion.
        out["channelJoinedDate"] = joined.replace("Joined", "").strip()
    return out


# The primary-info super-title links to a geo-restricted search for tagged
# videos; its a11y label is the reliable "is this a location?" signal (the same
# slot holds hashtags otherwise). The label is English (hl=en client).
_GEO_TAG_RE = re.compile(r"geo tagged with (.+)", re.IGNORECASE)


def parse_location(initial: dict) -> str | None:
    """Video geo-tag (place name) from ``videoPrimaryInfoRenderer.superTitleLink``.

    Returns ``None`` when the super-title is hashtags (or absent) rather than a
    location. The place name is read from the a11y label ("...geo tagged with
    Rome"), which is proper-cased where the visible runs are upper-cased.
    """
    st = dig(find_first(initial, "videoPrimaryInfoRenderer"), "superTitleLink")
    if not isinstance(st, dict):
        return None
    label = dig(st, "accessibility", "accessibilityData", "label") or ""
    match = _GEO_TAG_RE.search(label)
    return match.group(1).strip() if match else None


def parse_translation(next_data: dict) -> tuple[str | None, str | None]:
    """(title, description) from a ``/next`` response fetched with a target ``hl``.

    YouTube renders the creator-localized title/description into
    ``videoPrimaryInfoRenderer`` / ``videoSecondaryInfoRenderer`` for the request
    language. Videos without a localization return their original text.
    """
    vpir = find_first(next_data, "videoPrimaryInfoRenderer") or {}
    title = (
        "".join(r.get("text", "") for r in (dig(vpir, "title", "runs") or [])) or None
    )

    vsir = find_first(next_data, "videoSecondaryInfoRenderer") or {}
    description = dig(vsir, "attributedDescription", "content")
    if description is None:
        description = (
            "".join(r.get("text", "") for r in (dig(vsir, "description", "runs") or []))
            or None
        )
    return title, description


def parse_collaborators(initial: dict) -> list[dict[str, str | None]] | None:
    """Collaborator channels from the multi-owner "Collaborators" dialog.

    Collaboration videos replace the owner's plain ``title`` with an
    ``attributedTitle`` whose tap opens a dialog listing each credited channel
    (``listItemViewModel``). Returns ``None`` for ordinary single-owner videos.
    """
    owner = dig(
        find_first(initial, "videoSecondaryInfoRenderer"), "owner", "videoOwnerRenderer"
    )
    attributed = owner.get("attributedTitle") if isinstance(owner, dict) else None
    if not isinstance(attributed, dict):
        return None

    # The dialog's own list holds one row per channel. Read those rows directly
    # (not find_all) — each row's subscribe button nests its own menu items.
    dialog = find_first(attributed, "dialogViewModel")
    rows = dig(find_first(dialog, "listViewModel"), "listItems") or []

    collaborators: list[dict[str, str | None]] = []
    for row in rows:
        item = row.get("listItemViewModel") if isinstance(row, dict) else None
        name = dig(item, "title", "content")
        if not name:
            continue
        base = dig(find_first(item, "browseEndpoint"), "canonicalBaseUrl")
        collaborators.append(
            {
                "name": name,
                "username": base[2:]
                if isinstance(base, str) and base.startswith("/@")
                else None,
                "url": f"https://www.youtube.com{base}"
                if isinstance(base, str) and base
                else None,
            }
        )
    return collaborators or None


def parse_video_page(html: str) -> dict[str, Any] | None:
    """Parse a video/shorts watch page into a partial VideoItem dict.

    Merges ``ytInitialPlayerResponse.videoDetails`` (title, views, length,
    description, thumbnails) with ``ytInitialData`` (likes, comment count,
    channel info) and the microformat renderer (real publish date).
    """
    player = extract_yt_initial_player_response(html)
    initial = extract_yt_initial_data(html)
    if not player:
        return None

    details = player.get("videoDetails") or {}
    microformat = dig(player, "microformat", "playerMicroformatRenderer") or {}
    video_id = details.get("videoId")

    result: dict[str, Any] = {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        "title": details.get("title"),
        "text": details.get("shortDescription"),
        "viewCount": parse_count(details.get("viewCount")),
        "duration": seconds_to_duration(details.get("lengthSeconds")),
        "date": parse_date(microformat),
        "thumbnailUrl": _best_thumbnail(dig(details, "thumbnail", "thumbnails")),
        "hashtags": details.get("keywords") or [],
        "channelName": details.get("author"),
        "channelId": details.get("channelId"),
        "isAgeRestricted": _is_age_restricted(player, microformat),
        # Monetized ⇔ the player response carries ad slots. ponytail: absence
        # isn't proof (a logged-out fetch may omit ads), so False→None, not False.
        "isMonetized": bool(player.get("adPlacements") or player.get("playerAds"))
        or None,
        "isMembersOnly": _is_members_only(player, initial or {}),
        # "Includes paid promotion" disclosure overlay.
        "isPaidContent": find_first(player, "paidContentOverlayRenderer") is not None,
    }

    if initial:
        # Likes: the LIKE button's label carries the count string.
        likes = [
            b.get("title")
            for b in find_all(initial, "buttonViewModel")
            if isinstance(b, dict) and b.get("iconName") == "LIKE"
        ]
        result["likes"] = parse_count(likes[0]) if likes else None

        # Comment count lives in the engagement panel contextual info.
        contextual = find_first(initial, "contextualInfo")
        result["commentsCount"] = parse_count(dig(contextual, "runs", 0, "text"))
        result["commentsTurnedOff"] = _comments_turned_off(initial)
        result["descriptionLinks"] = parse_description_links(initial)
        result["location"] = parse_location(initial)
        result["collaborators"] = parse_collaborators(initial)

        # Channel handle / URL from the canonical base url ("/@Handle").
        base = find_first(initial, "canonicalBaseUrl")
        if isinstance(base, str) and base:
            result["channelUrl"] = f"https://www.youtube.com{base}"
            # Only "/@handle" yields a username; "/channel/UC..." is an id, not a handle.
            if base.startswith("/@"):
                result["channelUsername"] = base[2:] or None

        subs = find_first(initial, "subscriberCountText")
        result["numberOfSubscribers"] = parse_count(
            subs.get("simpleText") if isinstance(subs, dict) else subs
        )

        # Verified badge on the channel owner.
        badges = find_all(initial, "metadataBadgeRenderer")
        result["isChannelVerified"] = (
            any(isinstance(b, dict) and b.get("tooltip") == "Verified" for b in badges)
            or None
        )

    return result


def _view_count_from_renderer(renderer: dict) -> int | None:
    for key in ("shortViewCountText", "viewCountText"):
        node = renderer.get(key)
        if isinstance(node, dict):
            text = node.get("simpleText") or dig(node, "runs", 0, "text")
            count = parse_count(text)
            if count is not None:
                return count
    return None


def parse_search_response(data: dict) -> tuple[list[dict[str, Any]], str | None]:
    """Parse an InnerTube search response into partial VideoItem dicts + token."""
    results: list[dict[str, Any]] = []
    for r in find_all(data, "videoRenderer"):
        if not isinstance(r, dict) or "videoId" not in r:
            continue
        vid = r["videoId"]
        results.append(
            {
                "id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": dig(r, "title", "runs", 0, "text"),
                "text": dig(
                    r, "detailedMetadataSnippets", 0, "snippetText", "runs", 0, "text"
                ),
                "date": None,  # list pages only expose relative time
                "publishedTimeText": dig(r, "publishedTimeText", "simpleText"),
                "duration": dig(r, "lengthText", "simpleText"),
                "viewCount": _view_count_from_renderer(r),
                "thumbnailUrl": _best_thumbnail(dig(r, "thumbnail", "thumbnails")),
                **_channel_from_byline(r),
            }
        )
    return results, _continuation_token(data)


def _continuation_token(data: dict) -> str | None:
    tokens = [
        t.get("token")
        for t in find_all(data, "continuationCommand")
        if isinstance(t, dict) and t.get("token")
    ]
    return tokens[-1] if tokens else None


def parse_playlist_video_ids(data: dict) -> tuple[list[str], str | None]:
    """Ordered, de-duped video ids + paging token from a playlist ``/browse``.

    Playlist entries are ``lockupViewModel`` (the old ``playlistVideoRenderer``
    is retired); ``contentId`` holds the id. The 11-char guard keeps only videos
    and drops any playlist/channel lockup (e.g. the sidebar self-lockup). The
    token pages long playlists; callers must still guard against an empty page,
    since a short playlist can emit a spurious (non-paging) continuation.
    """
    seen: set[str] = set()
    ids: list[str] = []
    for lockup in find_all(data, "lockupViewModel"):
        vid = lockup.get("contentId") if isinstance(lockup, dict) else None
        if vid and len(vid) == 11 and vid not in seen:
            seen.add(vid)
            ids.append(vid)
    return ids, _continuation_token(data)


def parse_channel_videos(data: dict) -> tuple[list[dict[str, Any]], str | None]:
    """Parse an InnerTube channel-videos browse response (richItem lockups)."""
    results: list[dict[str, Any]] = []
    for item in find_all(data, "richItemRenderer"):
        lockup = dig(item, "content", "lockupViewModel")
        if not isinstance(lockup, dict):
            continue
        vid = lockup.get("contentId")
        if not vid:
            continue
        meta = dig(lockup, "metadata", "lockupMetadataViewModel")
        rows = dig(meta, "metadata", "contentMetadataViewModel", "metadataRows") or []
        parts = dig(rows, 0, "metadataParts") or []
        results.append(
            {
                "id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": dig(meta, "title", "content"),
                "viewCount": parse_count(dig(parts, 0, "text", "content")),
                "date": None,
                "publishedTimeText": dig(parts, 1, "text", "content"),
                "duration": _lockup_duration(lockup),
                "thumbnailUrl": _best_thumbnail(
                    dig(
                        lockup, "contentImage", "thumbnailViewModel", "image", "sources"
                    )
                ),
            }
        )
    return results, _continuation_token(data)


def parse_channel_shorts(data: dict) -> tuple[list[dict[str, Any]], str | None]:
    """Parse a channel Shorts browse/seed response (``shortsLockupViewModel``).

    Shorts use a different lockup than videos/streams: the id is on the reel
    watch endpoint, and title/views live in ``overlayMetadata``.
    """
    results: list[dict[str, Any]] = []
    for s in find_all(data, "shortsLockupViewModel"):
        if not isinstance(s, dict):
            continue
        vid = dig(s, "onTap", "innertubeCommand", "reelWatchEndpoint", "videoId")
        if not vid:
            entity = s.get("entityId") or ""
            vid = entity.rsplit("-", 1)[-1] if entity else None
        if not vid:
            continue
        results.append(
            {
                "id": vid,
                "url": f"https://www.youtube.com/shorts/{vid}",
                "title": dig(s, "overlayMetadata", "primaryText", "content"),
                "viewCount": parse_count(
                    dig(s, "overlayMetadata", "secondaryText", "content")
                ),
                "date": None,
                "thumbnailUrl": _best_thumbnail(
                    dig(s, "thumbnailViewModel", "image", "sources")
                ),
            }
        )
    return results, _continuation_token(data)


def _lockup_duration(lockup: dict) -> str | None:
    overlays = dig(lockup, "contentImage", "thumbnailViewModel", "overlays") or []
    for overlay in overlays:
        text = dig(
            overlay,
            "thumbnailBottomOverlayViewModel",
            "badges",
            0,
            "thumbnailBadgeViewModel",
            "text",
        )
        if text:
            return text
    return None


# ---------------------------------------------------------------------------
# Comments (/next endpoint)
# ---------------------------------------------------------------------------


def comment_section_token(initial_data: dict) -> str | None:
    """The watch page's comments-section continuation (seeds the /next call)."""
    for section in find_all(initial_data, "itemSectionRenderer"):
        if (
            isinstance(section, dict)
            and section.get("sectionIdentifier") == "comment-item-section"
        ):
            token = dig(
                find_first(section, "continuationItemRenderer"),
                "continuationEndpoint",
                "continuationCommand",
                "token",
            )
            if token:
                return token
    return None


def comment_sort_tokens(data: dict) -> dict[str, str]:
    """Map the comment sort labels ("Top"/"Newest") to their continuations."""
    tokens: dict[str, str] = {}
    sub = find_first(data, "sortFilterSubMenuRenderer")
    for item in dig(sub, "subMenuItems") or []:
        title = item.get("title") if isinstance(item, dict) else None
        token = dig(item, "serviceEndpoint", "continuationCommand", "token")
        if title and token:
            tokens[title] = token
    return tokens


def _comment_continuation_items(data: dict) -> list[Any]:
    items: list[Any] = []
    for key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
        for action in find_all(data, key):
            if isinstance(action, dict):
                items += action.get("continuationItems") or []
    return items


def comment_next_token(data: dict) -> str | None:
    """Pagination token: the trailing bare ``continuationItemRenderer``.

    Reply loaders are nested inside ``commentThreadRenderer``s; the page's own
    "load more" token is the last top-level continuation item, so scan the
    action's ``continuationItems`` from the end.
    """
    for item in reversed(_comment_continuation_items(data)):
        if isinstance(item, dict) and "continuationItemRenderer" in item:
            token = dig(
                item,
                "continuationItemRenderer",
                "continuationEndpoint",
                "continuationCommand",
                "token",
            )
            if token:
                return token
    return None


def comment_reply_tokens(data: dict) -> dict[str, str]:
    """Map each top-level comment id to its replies continuation token."""
    tokens: dict[str, str] = {}
    for thread in find_all(data, "commentThreadRenderer"):
        cid = dig(thread, "commentViewModel", "commentViewModel", "commentId")
        token = dig(
            find_first(thread, "continuationItemRenderer"),
            "continuationEndpoint",
            "continuationCommand",
            "token",
        )
        if cid and token:
            tokens[cid] = token
    return tokens


def parse_comment_entity(cep: dict) -> dict[str, Any]:
    """Map one ``commentEntityPayload`` to a partial CommentItem dict."""
    props = cep.get("properties") or {}
    author = cep.get("author") or {}
    toolbar = cep.get("toolbar") or {}
    return {
        "cid": props.get("commentId"),
        "comment": dig(props, "content", "content"),
        "author": author.get("displayName"),
        "publishedTimeText": props.get("publishedTime"),
        "voteCount": parse_count(toolbar.get("likeCountNotliked")),
        "replyCount": parse_count(toolbar.get("replyCount")),
        "authorIsChannelOwner": bool(author.get("isCreator")),
        # A creator heart attaches the channel owner's avatar to the toolbar.
        "hasCreatorHeart": bool(toolbar.get("creatorThumbnailUrl")),
        "type": "comment" if (props.get("replyLevel") or 0) == 0 else "reply",
    }


def parse_comment_entities(data: dict) -> list[dict[str, Any]]:
    """All comment payloads in a /next response, in display order."""
    return [
        parse_comment_entity(cep)
        for cep in find_all(data, "commentEntityPayload")
        if isinstance(cep, dict)
    ]


def parse_channel_sort_tokens(initial_data: dict) -> dict[str, str]:
    """Map channel-videos sort labels ("Latest"/"Popular"/"Oldest") to tokens."""
    tokens: dict[str, str] = {}
    for chip in find_all(initial_data, "chipViewModel"):
        if not isinstance(chip, dict):
            continue
        label = chip.get("text")
        token = dig(
            chip, "tapCommand", "innertubeCommand", "continuationCommand", "token"
        )
        if label and token:
            tokens[label] = token
    return tokens
