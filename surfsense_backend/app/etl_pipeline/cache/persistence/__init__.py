"""Database access for cached parse rows."""

from __future__ import annotations

from .models import CachedParse
from .repository import CachedParseRepository

__all__ = [
    "CachedParse",
    "CachedParseRepository",
]
