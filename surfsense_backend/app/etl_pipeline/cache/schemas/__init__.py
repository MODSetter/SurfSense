"""Pure value objects for the parse cache."""

from __future__ import annotations

from .eviction_candidate import EvictionCandidate
from .parse_key import ParseKey

__all__ = [
    "EvictionCandidate",
    "ParseKey",
]
