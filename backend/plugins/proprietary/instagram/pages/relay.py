"""The query results Instagram inlines in a logged-out page's ``application/json`` scripts."""

from __future__ import annotations

import json
import re
from typing import Any

_APP_JSON = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)


def relay_values(html: str, key: str) -> list[dict[str, Any]]:
    """Every object held under ``key`` in the page's inlined results, in page order."""
    found: list[dict[str, Any]] = []
    for raw in _APP_JSON.findall(html):
        if f'"{key}"' not in raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            current = stack.pop(0)
            if isinstance(current, dict):
                value = current.get(key)
                if isinstance(value, dict):
                    found.append(value)
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
    return found
