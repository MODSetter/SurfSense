"""A profile page and its embed together, as the ``web_profile_info`` user ``parse_profile`` reads.

That endpoint answers ``require_login`` to every logged-out session (2026-10-12);
the two pages a logged-out visitor sees carry the same fields between them.
"""

from __future__ import annotations

from typing import Any

from .embed import embed_media


def profile_info(user: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    links = [
        link.get("url")
        for link in user.get("bio_links") or []
        if isinstance(link, dict) and link.get("url")
    ]
    followers = user.get("follower_count", context.get("followers_count"))
    media = embed_media(context)
    return {
        # ``pk`` is the id web_profile_info gave; ``id`` here is a Graph API id.
        "id": str(user.get("pk") or context.get("owner_id") or "") or None,
        "username": user.get("username") or context.get("username"),
        "full_name": user.get("full_name") or context.get("full_name"),
        "biography": user.get("biography"),
        "external_url": links[0] if links else None,
        "is_private": user.get("is_private"),
        "is_verified": user.get("is_verified", context.get("is_verified")),
        "profile_pic_url": user.get("profile_pic_url")
        or context.get("profile_pic_url"),
        "edge_followed_by": {"count": followers},
        "edge_follow": {"count": user.get("following_count")},
        "edge_owner_to_timeline_media": {
            "count": context.get("posts_count"),
            "edges": [{"node": node} for node in media],
        },
    }
