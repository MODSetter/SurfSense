"""Lock the custom Jinja filters: ``date`` and ``slugify``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.automations.templating.filters import filter_date, filter_slugify

pytestmark = pytest.mark.unit


def test_filter_slugify_produces_url_safe_slug_from_typical_title() -> None:
    """``filter_slugify`` lowercases, replaces non-alphanumerics with
    hyphens, collapses repeats, and trims edge hyphens — the standard
    URL-slug contract users expect when piping titles into paths."""
    assert filter_slugify("Hello, World! 2026") == "hello-world-2026"


def test_filter_date_formats_datetime_with_strftime_format() -> None:
    """``filter_date`` calls ``strftime`` on datetime-like values with the
    provided format. Default format yields ISO date (YYYY-MM-DD)."""
    dt = datetime(2026, 5, 28, 14, 30, tzinfo=UTC)

    assert filter_date(dt) == "2026-05-28"
    assert filter_date(dt, "%Y/%m/%d %H:%M") == "2026/05/28 14:30"


def test_filter_date_returns_empty_string_for_none() -> None:
    """``None`` (e.g., a never-fired ``last_fired_at``) renders as the
    empty string rather than the literal ``"None"`` or raising. This is
    what lets templates write ``{{ inputs.last_fired_at | date }}``
    unconditionally on the first run."""
    assert filter_date(None) == ""


def test_filter_date_passes_strings_through_unchanged() -> None:
    """Already-formatted ISO strings (the JSON-serialized shape of
    runtime inputs like ``fired_at``) pass through unchanged so callers
    don't have to special-case the type."""
    assert filter_date("2026-05-28T14:30:00+00:00") == "2026-05-28T14:30:00+00:00"
