"""Parse a captured ``/api/comment/list`` response into comment items.

The comment API returns ``{"comments": [...]}`` where each entry uses the
mobile-API snake_case shape (``cid``, ``digg_count``, ``reply_comment_total``,
``create_time``, and a nested ``user`` with ``uid``/``unique_id``/``nickname``/
``avatar_thumb``). ``reply_id != "0"`` marks a reply to a parent comment.
"""

from __future__ import annotations

from typing import Any

from .timestamps import epoch_to_iso


def comments_from_response(body: Any) -> list[dict[str, Any]]:
    """Return the raw comment records carried by one API response, or ``[]``."""
    if not isinstance(body, dict):
        return []
    comments = body.get("comments")
    if not isinstance(comments, list):
        return []
    return [c for c in comments if isinstance(c, dict)]


def _avatar(user: dict[str, Any]) -> str | None:
    thumb = user.get("avatar_thumb")
    if isinstance(thumb, dict):
        urls = thumb.get("url_list")
        if isinstance(urls, list) and urls:
            return urls[0]
    return None


def parse_comment(raw: dict[str, Any], video_url: str) -> dict[str, Any]:
    """Map a raw comment record to a :class:`CommentItem` output dict."""
    from ..schemas.items import CommentItem

    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    reply_id = raw.get("reply_id")
    create_time = raw.get("create_time")
    return CommentItem(
        id=raw.get("cid"),
        text=raw.get("text"),
        videoWebUrl=video_url,
        diggCount=raw.get("digg_count"),
        replyCommentTotal=raw.get("reply_comment_total"),
        createTime=create_time,
        createTimeISO=epoch_to_iso(create_time),
        uid=user.get("uid"),
        uniqueId=user.get("unique_id"),
        nickName=user.get("nickname"),
        avatar=_avatar(user),
        repliesToId=reply_id if reply_id and reply_id != "0" else None,
    ).to_output()
