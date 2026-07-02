"""Classify a YouTube URL and extract its identifier.

Covers the ``startUrls`` shapes the Apify spec accepts: video, channel,
playlist, hashtag, and search-results pages. Video-ID extraction reuses the
logic already in ``app/tasks/document_processors/youtube_processor.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

ResolvedKind = Literal["video", "channel", "playlist", "hashtag", "search"]

_PLAYLIST_ID_RE = re.compile(r"[?&]list=([\w-]+)")


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    value: str  # video id, channel handle/id, playlist id, hashtag, or query
    url: str


def get_youtube_video_id(url: str) -> str | None:
    """Extract a video ID from watch/youtu.be/embed/shorts URL formats."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if hostname == "youtu.be":
        return parsed.path[1:] or None
    if hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        for prefix in ("/embed/", "/v/", "/shorts/"):
            if parsed.path.startswith(prefix):
                return parsed.path[len(prefix) :].split("/")[0] or None
    return None


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify a YouTube URL into a scrape job, or ``None`` if unrecognized."""
    parsed = urlparse(url)
    path = parsed.path or ""

    # Shorts are videos with their own path.
    if "/shorts/" in path:
        vid = path.split("/shorts/")[1].split("/")[0]
        return ResolvedUrl("video", vid, url) if vid else None

    video_id = get_youtube_video_id(url)
    if video_id:
        return ResolvedUrl("video", video_id, url)

    # Playlist (either a /playlist page or any URL carrying ?list=).
    playlist_match = _PLAYLIST_ID_RE.search(url)
    if path.startswith("/playlist") and playlist_match:
        return ResolvedUrl("playlist", playlist_match.group(1), url)

    # Search results page.
    if path == "/results":
        query = parse_qs(parsed.query).get("search_query", [None])[0]
        if query:
            return ResolvedUrl("search", unquote(query), url)
        return None

    # Hashtag page (/hashtag/<tag>).
    if path.startswith("/hashtag/"):
        tag = path[len("/hashtag/") :].split("/")[0]
        return ResolvedUrl("hashtag", unquote(tag), url) if tag else None

    # Channel: /@handle, /channel/UC..., /c/Name, /user/Name.
    if path.startswith("/@"):
        return ResolvedUrl("channel", path[2:].split("/")[0], url)
    for prefix in ("/channel/", "/c/", "/user/"):
        if path.startswith(prefix):
            handle = path[len(prefix) :].split("/")[0]
            return ResolvedUrl("channel", handle, url) if handle else None

    # A trailing ?list= without an explicit /playlist path.
    if playlist_match:
        return ResolvedUrl("playlist", playlist_match.group(1), url)

    return None
