"""Navigate the rehydration blob to the scopes the flows consume."""

from __future__ import annotations

from typing import Any

_DEFAULT = "__DEFAULT_SCOPE__"


def _scope(data: dict[str, Any], name: str) -> dict[str, Any] | None:
    scope = (data.get(_DEFAULT) or {}).get(name)
    return scope if isinstance(scope, dict) else None


def video_item_struct(data: dict[str, Any]) -> dict[str, Any] | None:
    """The ``itemStruct`` of a video-detail page, or ``None``."""
    scope = _scope(data, "webapp.video-detail")
    if not scope:
        return None
    item = (scope.get("itemInfo") or {}).get("itemStruct")
    return item if isinstance(item, dict) else None


def user_info(data: dict[str, Any]) -> dict[str, Any] | None:
    """The ``userInfo`` (``{user, stats}``) of a profile page, or ``None``."""
    scope = _scope(data, "webapp.user-detail")
    if not scope:
        return None
    info = scope.get("userInfo")
    return info if isinstance(info, dict) else None
