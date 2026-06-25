"""Tests for building a document's source label."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.document_render import source_label

pytestmark = pytest.mark.unit


def test_known_type_uses_friendly_name() -> None:
    assert source_label("SLACK_CONNECTOR", {}) == "Slack"


def test_unmapped_type_is_prettified() -> None:
    assert source_label("GOOGLE_DRIVE_FILE", {}) == "Google Drive"


def test_url_host_is_appended_and_www_stripped() -> None:
    label = source_label("CRAWLED_URL", {"url": "https://www.docs.python.org/3/"})

    assert label == "Web · docs.python.org"


def test_host_only_when_type_unknown() -> None:
    assert source_label(None, {"url": "https://example.com/a"}) == "example.com"


def test_returns_none_when_nothing_known() -> None:
    assert source_label(None, {}) is None


def test_non_http_url_is_ignored() -> None:
    assert source_label("FILE", {"url": "/local/path"}) == "File"
