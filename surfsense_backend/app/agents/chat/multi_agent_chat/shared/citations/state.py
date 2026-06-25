"""Read the conversation's ``CitationRegistry`` out of graph state.

The registry is checkpointed, so it may come back as a live ``CitationRegistry``
or a plain dict (after (de)serialization). Both the search tool and the read
path load it the same way before registering new ``[n]`` and writing it back.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .registry import CitationRegistry


def load_registry(state: Mapping[str, Any] | None) -> CitationRegistry:
    """Return the registry from ``state``, tolerating a serialized dict or absence."""
    raw = state.get("citation_registry") if state else None
    if isinstance(raw, CitationRegistry):
        return raw
    if isinstance(raw, dict):
        return CitationRegistry.model_validate(raw)
    return CitationRegistry()


__all__ = ["load_registry"]
