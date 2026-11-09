"""A profile's logged-out page, and its reels tab: the profile, and the codes of its grid."""

from __future__ import annotations

from typing import Any, NamedTuple

from .relay import relay_values


class GridPost(NamedTuple):
    code: str
    pinned: bool | None  # ``None``: the page does not say
    # Only the reels grid counts plays; a logged-out post page does not.
    views: int | None = None
    # The posts grid's, for a post taken from the embed, which lacks both.
    product_type: str | None = None
    alt: str | None = None


def profile_user(html: str) -> dict[str, Any]:
    """``xig_user_by_username``: the page splits it over a query per tab, so merge them."""
    user: dict[str, Any] = {}
    for part in relay_values(html, "xig_user_by_username"):
        user.update(part)
    return user


def timeline(user: dict[str, Any]) -> list[GridPost]:
    """The posts grid; its nodes do not say which are pinned."""
    return [
        GridPost(
            code,
            None,
            product_type=node.get("product_type"),
            alt=node.get("accessibility_caption"),
        )
        for node in _nodes(user.get("polaris_ordered_timeline_connection"))
        if isinstance(code := node.get("code"), str)
    ]


def clips(user: dict[str, Any]) -> list[GridPost]:
    """The reels grid; a reel pinned to it names its owner in ``clips_tab_pinned_user_ids``."""
    return [
        GridPost(
            code,
            bool(node.get("clips_tab_pinned_user_ids")),
            node.get("play_count") if isinstance(node.get("play_count"), int) else None,
        )
        for node in _nodes(user.get("polaris_clips_connection"))
        if isinstance(code := node.get("code"), str)
    ]


def _nodes(connection: Any) -> list[dict[str, Any]]:
    if not isinstance(connection, dict):
        return []
    edges = connection.get("edges") or []
    return [
        e["node"]
        for e in edges
        if isinstance(e, dict) and isinstance(e.get("node"), dict)
    ]
