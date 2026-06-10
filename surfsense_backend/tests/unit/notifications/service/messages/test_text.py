"""Unit tests for shared notification text helpers."""

from __future__ import annotations

import pytest

from app.notifications.service.messages.text import truncate

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
