"""Shape tool results into the format the caller asked for.

Tools default to Markdown (readable for the model and the human watching), and
can return raw JSON when a caller wants to post-process the data. Large payloads
are clipped so a single call can't blow the context window.
"""

from __future__ import annotations

import json
from typing import Any, Literal

ResponseFormat = Literal["markdown", "json"]

DEFAULT_CLIP_CHARS = 20_000


def to_json(payload: Any) -> str:
    """Pretty-print a payload as JSON, tolerating non-serializable values."""
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def clip(text: str, limit: int = DEFAULT_CLIP_CHARS) -> str:
    """Trim overlong text, leaving a visible marker of how much was dropped."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n\n… [{dropped} more characters truncated]"
