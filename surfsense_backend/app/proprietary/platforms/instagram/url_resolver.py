"""Classify and normalize an Instagram URL into a scrape job.

Covers the anonymously-scrapable ``directUrls`` shapes: a profile, a post
(``/p/``), and a reel (``/reel/``), plus bare profile IDs. Hashtag and place
URLs are deliberately unsupported — their feeds are login-walled for anonymous
callers (use Google-backed discovery + single-post extraction instead).
Non-Instagram hosts resolve to ``None`` so the orchestrator can skip them.
Mirrors the frozen ``ResolvedUrl`` dataclass shape of ``../reddit/url_resolver.py``.

Normalization rules (from the reference spec):
- ``_u/`` and ``/profilecard/`` segments are stripped.
- Story URLs (``/stories/<user>/...``) reduce to the profile.
- Numeric post-ID URLs cannot be single-post-extracted anonymously (the HTML
  page keys on the shortCode), so they resolve with ``numeric_post_id`` set and
  the media flow skips them.
- ``share/`` links are unsupported (they need a network redirect to resolve to a
  canonical post/profile URL); pass the resolved ``/p/`` or profile URL instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

ResolvedKind = Literal["profile", "post", "reel"]

_INSTAGRAM_HOSTS = frozenset(
    {"m.instagram.com", "www.instagram.com", "instagram.com"}
)
_STRIP_SEGMENTS = frozenset({"_u", "profilecard"})
_RESERVED = frozenset(
    {"p", "s", "tv", "reel", "reels", "share", "explore", "stories", "accounts"}
)


@dataclass(frozen=True)
class ResolvedUrl:
    """A classified Instagram target: the kind, its key, and the source URL."""

    kind: ResolvedKind
    value: str
    url: str
    numeric_post_id: bool = False


def _is_instagram_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.lower() in _INSTAGRAM_HOSTS


def _segments(url: str) -> list[str]:
    parsed = urlparse(url)
    if not _is_instagram_host(parsed.hostname):
        return []
    if not parsed.path:
        return []
    return [s for s in parsed.path.split("/") if s and s not in _STRIP_SEGMENTS]


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify an Instagram URL into a scrape job, or ``None`` if unrecognized.

    A bare token with no ``http`` prefix and no ``/`` is treated as a profile ID
    (the reference accepts bare profile handles alongside full URLs).
    """
    if "instagram.com" not in url.lower():
        token = url.strip().lstrip("@")
        if token and "/" not in token and "." not in token:
            return ResolvedUrl(
                "profile", token, f"https://www.instagram.com/{token}/"
            )
    segments = _segments(url)
    if not segments:
        return None
    head = segments[0]
    if head == "p" and len(segments) >= 2:
        code = segments[1]
        return ResolvedUrl("post", code, url, numeric_post_id=code.isdigit())
    if head in ("reel", "reels") and len(segments) >= 2:
        code = segments[1]
        return ResolvedUrl("reel", code, url, numeric_post_id=code.isdigit())
    if head == "stories" and len(segments) >= 2:
        user = segments[1]
        return ResolvedUrl(
            "profile", user, f"https://www.instagram.com/{user}/"
        )
    if head not in _RESERVED:
        return ResolvedUrl("profile", head, url)
    return None
