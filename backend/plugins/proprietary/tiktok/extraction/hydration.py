"""Extract the ``__UNIVERSAL_DATA_FOR_REHYDRATION__`` JSON embedded in page HTML.

TikTok server-renders the first page of data into a single script tag; parsing
it yields page-one items (video/profile/hashtag) without any signed API call.
"""

from __future__ import annotations

import json
import re
from typing import Any

_BLOB_RE = re.compile(
    r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def extract_rehydration_data(html: str) -> dict[str, Any] | None:
    """Return the parsed rehydration blob, or ``None`` if absent/unparseable."""
    match = _BLOB_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
