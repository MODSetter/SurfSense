"""Classify a TikTok URL into a :class:`TikTokTarget`, or ``None``."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from .types import SearchSection, TikTokTarget

_TIKTOK_HOSTS = frozenset({"tiktok.com", "www.tiktok.com", "m.tiktok.com"})
_SEARCH_SECTIONS: frozenset[SearchSection] = frozenset({"video", "user"})


def _is_tiktok_host(hostname: str | None) -> bool:
    return bool(hostname) and hostname.lower() in _TIKTOK_HOSTS


def resolve_target(url: str) -> TikTokTarget | None:
    parsed = urlparse(url)
    if not _is_tiktok_host(parsed.hostname):
        return None

    segments = [s for s in (parsed.path or "").split("/") if s]
    if not segments:
        return None

    # Profile / video live under /@username[...].
    if segments[0].startswith("@"):
        username = segments[0][1:]
        if not username:
            return None
        if len(segments) >= 3 and segments[1] == "video" and segments[2]:
            return TikTokTarget("video", segments[2], url, username=username)
        return TikTokTarget("profile", username, url)

    if segments[0] == "tag" and len(segments) >= 2 and segments[1]:
        return TikTokTarget("hashtag", unquote(segments[1]), url)

    if segments[0] == "search":
        query = parse_qs(parsed.query).get("q", [None])[0]
        if not query:
            return None
        section = segments[1] if len(segments) >= 2 else None
        return TikTokTarget(
            "search",
            unquote(query),
            url,
            section=section if section in _SEARCH_SECTIONS else None,
        )

    return None
