"""Shape tool results into the format the caller asked for.

Tools default to Markdown (readable for the model and the human watching), and
can return raw JSON when a caller wants to post-process the data. Large payloads
are clipped so a single call can't blow the context window.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import Field

ResponseFormat = Literal["markdown", "json"]

# Shared parameter type for every tool: same name, same semantics everywhere.
ResponseFormatParam = Annotated[
    ResponseFormat,
    Field(
        description="'markdown' (default, human-readable) or 'json' "
        "(raw data for post-processing)."
    ),
]

DEFAULT_CLIP_CHARS = 20_000
ITEM_FIELD_CLIP_CHARS = 1_500

# Fields that duplicate another field verbatim (e.g. Reddit's 'html' mirrors
# 'body') and only bloat inline results. The full record stays in the run.
_REDUNDANT_ITEM_FIELDS = frozenset({"html"})


def compact_items(result: Any, field_limit: int = ITEM_FIELD_CLIP_CHARS) -> Any:
    """Shrink a scraper result for inline return.

    Drops redundant fields and clips overlong strings per field, so a response
    keeps every item as an excerpt instead of a few items in full. The
    untruncated result remains retrievable via its stored run.
    """
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return {
            **result,
            "items": [_compact_item(item, field_limit) for item in result["items"]],
        }
    return result


def _compact_item(item: Any, field_limit: int) -> Any:
    # ponytail: compacts top-level string fields only; nested structures pass
    # through untouched. Upgrade path is a recursive walk if a platform nests
    # long text.
    if not isinstance(item, dict):
        return item
    return {
        key: clip(value, field_limit) if isinstance(value, str) else value
        for key, value in item.items()
        if key not in _REDUNDANT_ITEM_FIELDS
    }


def to_json(payload: Any) -> str:
    """Pretty-print a payload as JSON, tolerating non-serializable values."""
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def clip(text: str, limit: int = DEFAULT_CLIP_CHARS) -> str:
    """Trim overlong text, leaving a visible marker of how much was dropped."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n\n… [{dropped} more characters truncated]"
