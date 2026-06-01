"""Filter and test names admitted into the sandboxed environment."""

from __future__ import annotations

ALLOWED_FILTERS: tuple[str, ...] = (
    "default",
    "first",
    "join",
    "last",
    "length",
    "lower",
    "replace",
    "reverse",
    "sort",
    "tojson",
    "trim",
    "truncate",
    "upper",
    "date",
    "slugify",
)

ALLOWED_TESTS: tuple[str, ...] = (
    "defined",
    "none",
    "number",
    "string",
    "mapping",
    "sequence",
    "boolean",
)
