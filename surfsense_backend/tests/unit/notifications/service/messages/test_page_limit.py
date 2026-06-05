"""Unit tests for page-limit presentation logic."""

from __future__ import annotations

import pytest

from app.notifications.service.messages import page_limit as msg

pytestmark = pytest.mark.unit


def test_operation_id_encodes_search_space():
    """The operation id embeds the search space id."""
    assert msg.operation_id("doc.pdf", 9).startswith("page_limit_9_")


def test_summary_title_and_message():
    """The summary states the document and the used/limit page counts."""
    title, message = msg.summary("short.pdf", pages_used=95, pages_limit=100, pages_to_add=10)
    assert title == "Page limit exceeded: short.pdf"
    assert message == (
        "This document has ~10 page(s) but you've used 95/100 pages. "
        "Upgrade to process more documents."
    )


def test_summary_truncates_long_name():
    """A long document name is truncated in the title."""
    title, _ = msg.summary("a" * 50, pages_used=1, pages_limit=2, pages_to_add=1)
    assert title == f"Page limit exceeded: {'a' * 40}..."
