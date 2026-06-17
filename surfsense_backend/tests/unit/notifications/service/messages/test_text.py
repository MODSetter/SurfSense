"""Unit tests for shared notification text helpers."""

from __future__ import annotations

import pytest

from app.notifications.service.messages.text import format_title, truncate

pytestmark = pytest.mark.unit


def test_truncate_leaves_short_text_unchanged():
    """Text under the limit is returned verbatim, with no ellipsis."""
    assert truncate("hello", 100) == "hello"


def test_truncate_keeps_text_at_exact_limit():
    """Text exactly at the limit is not truncated."""
    assert truncate("a" * 40, 40) == "a" * 40


def test_truncate_appends_ellipsis_when_over_limit():
    """Text past the limit is cut to the limit and gains an ellipsis."""
    assert truncate("a" * 41, 40) == "a" * 40 + "..."


def test_format_title_keeps_short_name():
    """Short names are joined to the prefix without truncation."""
    assert format_title("Ready: ", "report.pdf") == "Ready: report.pdf"


def test_format_title_truncates_long_name():
    """Long names are truncated so the full title fits the DB limit."""
    long_name = "a" * 250
    title = format_title("Processing: ", long_name)
    assert len(title) == 200
    assert title.startswith("Processing: ")
    assert title.endswith("...")


def test_format_title_respects_custom_max_length():
    """A custom max length caps the title."""
    assert len(format_title("Go: ", "hello world", max_length=10)) == 10
