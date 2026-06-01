"""Custom Jinja filters registered into the sandboxed environment."""

from __future__ import annotations

import re
from typing import Any


def filter_date(value: Any, fmt: str = "%Y-%m-%d") -> str:
    """Format a datetime-like value with ``strftime``. Strings pass through."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    raise ValueError(f"date filter requires datetime-like, got {type(value).__name__}")


_SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")
_SLUG_DASHES = re.compile(r"-+")


def filter_slugify(value: Any) -> str:
    """Lowercase, replace non-alphanumerics with hyphens, collapse and trim."""
    s = str(value).lower()
    s = _SLUG_NONALNUM.sub("-", s)
    s = _SLUG_DASHES.sub("-", s)
    return s.strip("-")
