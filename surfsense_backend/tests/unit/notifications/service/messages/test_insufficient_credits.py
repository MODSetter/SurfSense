"""Unit tests for insufficient-credits presentation logic."""

from __future__ import annotations

import pytest

from app.notifications.service.messages import insufficient_credits as msg

pytestmark = pytest.mark.unit


def test_operation_id_encodes_workspace():
    """The operation id embeds the workspace id."""
    assert msg.operation_id("doc.pdf", 9).startswith("insufficient_credits_9_")


def test_summary_title_and_message():
    """The summary states the document and the required/available credit."""
    title, message = msg.summary(
        "short.pdf", balance_micros=250_000, required_micros=1_000_000
    )
    assert title == "Insufficient credits: short.pdf"
    assert message == (
        "This document costs about $1.00 to process but you have "
        "$0.25 of credit left. Add more credits to continue."
    )


def test_summary_clamps_negative_balance_to_zero():
    """A negative balance is clamped to $0.00 in the message."""
    _, message = msg.summary("doc.pdf", balance_micros=-5_000, required_micros=500_000)
    assert "$0.00 of credit left" in message


def test_summary_truncates_long_name():
    """A long document name is truncated in the title."""
    title, _ = msg.summary("a" * 50, balance_micros=0, required_micros=1_000)
    assert title == f"Insufficient credits: {'a' * 40}..."
