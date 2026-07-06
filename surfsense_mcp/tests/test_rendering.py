"""Output shaping: clipping oversized text and JSON serialization."""

from __future__ import annotations

from surfsense_mcp.core.rendering import clip, to_json


def test_clip_leaves_short_text_untouched():
    assert clip("short", limit=100) == "short"


def test_clip_truncates_and_marks_dropped_characters():
    clipped = clip("x" * 50, limit=10)
    assert clipped.startswith("x" * 10)
    assert "40 more characters truncated" in clipped


def test_to_json_serializes_non_native_values():
    from datetime import datetime

    rendered = to_json({"at": datetime(2026, 1, 2, 3, 4, 5)})
    assert "2026-01-02" in rendered
