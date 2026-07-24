"""Item structs from a captured ``item_list`` / search API response body.

Profile and hashtag listings return ``{"itemList": [...]}``; search returns
``{"data": [{"item": {...}}]}``. Both element shapes are the same itemStruct
:func:`parse_video` already consumes.
"""

from __future__ import annotations

from typing import Any


def items_from_response(body: Any) -> list[dict[str, Any]]:
    """Return the itemStructs carried by one API response, or ``[]``."""
    if not isinstance(body, dict):
        return []

    item_list = body.get("itemList")
    if isinstance(item_list, list):
        return [i for i in item_list if isinstance(i, dict)]

    data = body.get("data")
    if isinstance(data, list):
        return [
            entry["item"]
            for entry in data
            if isinstance(entry, dict) and isinstance(entry.get("item"), dict)
        ]

    return []
