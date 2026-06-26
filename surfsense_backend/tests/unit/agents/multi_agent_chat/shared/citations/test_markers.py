"""Tests for citation-entry → frontend payload mapping."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations.markers import (
    to_frontend_payload,
)
from app.agents.chat.multi_agent_chat.shared.citations.models import (
    CitationEntry,
    CitationSourceType,
)

pytestmark = pytest.mark.unit


def _entry(source_type: CitationSourceType, locator: dict) -> CitationEntry:
    return CitationEntry(n=1, source_type=source_type, locator=locator)


def test_kb_chunk_maps_to_chunk_id() -> None:
    entry = _entry(CitationSourceType.KB_CHUNK, {"chunk_id": 42, "document_id": 7})

    assert to_frontend_payload(entry) == "42"


def test_anon_chunk_keeps_negative_id() -> None:
    entry = _entry(CitationSourceType.ANON_CHUNK, {"chunk_id": -3})

    assert to_frontend_payload(entry) == "-3"


def test_web_result_maps_to_url() -> None:
    entry = _entry(CitationSourceType.WEB_RESULT, {"url": "https://example.com/a"})

    assert to_frontend_payload(entry) == "https://example.com/a"


def test_not_yet_renderable_kind_is_dropped() -> None:
    entry = _entry(CitationSourceType.CHAT_TURN, {"thread_id": 1, "turn": 2})

    assert to_frontend_payload(entry) is None


def test_missing_locator_field_is_dropped() -> None:
    entry = _entry(CitationSourceType.KB_CHUNK, {})

    assert to_frontend_payload(entry) is None
