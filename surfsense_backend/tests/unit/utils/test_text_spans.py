"""Unit tests for char-span -> line-range conversion."""

from __future__ import annotations

import pytest

from app.utils.text_spans import char_span_to_line_range

pytestmark = pytest.mark.unit

_TEXT = "line1\nline2\nline3"


def test_single_line_span() -> None:
    start = _TEXT.index("line2")
    assert char_span_to_line_range(_TEXT, start, start + len("line2")) == (2, 2)


def test_first_line_span() -> None:
    assert char_span_to_line_range(_TEXT, 0, len("line1")) == (1, 1)


def test_last_line_span() -> None:
    start = _TEXT.index("line3")
    assert char_span_to_line_range(_TEXT, start, len(_TEXT)) == (3, 3)


def test_multi_line_span() -> None:
    # "line1\nline2" spans lines 1-2.
    assert char_span_to_line_range(_TEXT, 0, _TEXT.index("line2") + 5) == (1, 2)


def test_empty_span_resolves_to_its_line() -> None:
    start = _TEXT.index("line2")
    assert char_span_to_line_range(_TEXT, start, start) == (2, 2)


def test_offsets_clamped_to_text_bounds() -> None:
    assert char_span_to_line_range(_TEXT, -5, 10_000) == (1, 3)
