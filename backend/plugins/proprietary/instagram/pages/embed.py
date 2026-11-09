"""A profile's embed page: its exact counts and its newest posts in full, pinned ones left out."""

from __future__ import annotations

import json
import re
from typing import Any

# The embed's state rides in its script as a JSON string, escaped once more.
_CONTEXT = re.compile(r'"contextJSON"\s*:\s*("(?:[^"\\]|\\.)*")')


def embed_context(html: str) -> dict[str, Any]:
    match = _CONTEXT.search(html)
    if match is None:
        return {}
    try:
        context = json.loads(json.loads(match.group(1))).get("context")
    except (ValueError, AttributeError):
        return {}
    return context if isinstance(context, dict) else {}


def embed_media(context: dict[str, Any]) -> list[dict[str, Any]]:
    """The embed's posts as the ``shortcode_media`` nodes ``parse_media`` reads."""
    return [
        media
        for item in context.get("graphql_media") or []
        if isinstance(item, dict)
        and isinstance(media := item.get("shortcode_media"), dict)
    ]
