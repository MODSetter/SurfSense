"""Normalize TikTok author/profile payloads into an ``authorMeta`` dict."""

from __future__ import annotations

from typing import Any

_PROFILE_URL = "https://www.tiktok.com/@{username}"


def build_author_meta(author: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    """Map an author object + its stats to the ``authorMeta`` output shape."""
    username = author.get("uniqueId")
    return {
        "id": author.get("id"),
        "name": username,
        "nickName": author.get("nickname"),
        "profileUrl": _PROFILE_URL.format(username=username) if username else None,
        "verified": author.get("verified"),
        "signature": author.get("signature"),
        "avatar": author.get("avatarLarger") or author.get("avatarMedium"),
        "privateAccount": author.get("privateAccount"),
        "fans": stats.get("followerCount"),
        "following": stats.get("followingCount"),
        "heart": stats.get("heartCount"),
        "video": stats.get("videoCount"),
    }


def parse_author(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map a ``webapp.user-detail`` ``userInfo`` (``{user, stats}``) to authorMeta."""
    return build_author_meta(user_info.get("user") or {}, user_info.get("stats") or {})
