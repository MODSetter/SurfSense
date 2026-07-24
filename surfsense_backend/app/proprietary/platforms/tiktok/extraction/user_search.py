"""Parse the ``/api/search/user`` response into profile items.

User search returns ``{"user_list": [{"user_info": {...}}, ...]}`` where each
``user_info`` uses the mobile-API snake_case shape (``uid``, ``unique_id``,
``follower_count``, ``total_favorited``, ``avatar_thumb.url_list``) — distinct
from the camelCase ``webapp.user-detail`` blob the profile flow reads, so it gets
its own mapping into the shared :class:`TikTokProfileItem` output contract.
"""

from __future__ import annotations

from typing import Any

_PROFILE_URL = "https://www.tiktok.com/@{username}"


def users_from_response(body: Any) -> list[dict[str, Any]]:
    """Return the ``user_info`` objects carried by one search response, or ``[]``."""
    if not isinstance(body, dict):
        return []
    user_list = body.get("user_list")
    if not isinstance(user_list, list):
        return []
    return [
        entry["user_info"]
        for entry in user_list
        if isinstance(entry, dict) and isinstance(entry.get("user_info"), dict)
    ]


def _avatar(user_info: dict[str, Any]) -> str | None:
    thumb = user_info.get("avatar_thumb")
    if isinstance(thumb, dict):
        urls = thumb.get("url_list")
        if isinstance(urls, list) and urls:
            return urls[0]
    return None


def parse_search_user(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map a search ``user_info`` to a :class:`TikTokProfileItem` output dict."""
    from ..schemas.items import TikTokProfileItem

    username = user_info.get("unique_id")
    return TikTokProfileItem(
        id=user_info.get("uid"),
        name=username,
        nickName=user_info.get("nickname"),
        profileUrl=_PROFILE_URL.format(username=username) if username else None,
        verified=bool(user_info.get("enterprise_verify_reason")),
        signature=user_info.get("signature"),
        avatar=_avatar(user_info),
        fans=user_info.get("follower_count"),
        heart=user_info.get("total_favorited"),
        secUid=user_info.get("sec_uid"),
    ).to_output()
