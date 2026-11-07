"""How much text a model's window holds, as a runner budgets what every call re-reads."""

from __future__ import annotations

# A token is about 3.5 characters of English; 3 leaves room for numbers and tables.
CHARS_PER_TOKEN = 3
# What a window of unknown size is taken to be: the floor every agent model meets.
UNKNOWN_WINDOW = 32_768


def window_chars(window: int | None, share: float, ceiling: int) -> int:
    """The characters `share` of the window holds, never past `ceiling`."""
    return min(int((window or UNKNOWN_WINDOW) * share * CHARS_PER_TOKEN), ceiling)
