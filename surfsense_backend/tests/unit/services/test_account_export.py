"""Contract-3 producer: citation flattening and the committed fixture."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.export_service import (
    _citation_payloads,
    _citation_titles,
    flatten_message_text,
    flatten_workspace_chats,
)

pytestmark = pytest.mark.unit


def _contracts_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "contracts"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("docs/contracts not found")


def test_committed_export_sample_matches_the_contract():
    spec = importlib.util.spec_from_file_location(
        "check_export_sample", _contracts_dir() / "check-export-sample.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(_contracts_dir() / "export-sample") == 0


def test_three_citation_markers_export_with_none_and_three_titles():
    text = "A [citation:11] then [citation:22] and [citation:33] done."
    titles = {"11": "Alpha", "22": "Beta", "33": "Gamma"}
    stripped, citations = flatten_message_text(text, titles)
    assert "[citation:" not in stripped
    assert citations == [
        {"title": "Alpha"},
        {"title": "Beta"},
        {"title": "Gamma"},
    ]


def test_duplicate_citation_titles_keep_first_seen_order():
    stripped, citations = flatten_message_text(
        "See [citation:1] and again [citation:1] then [citation:2].",
        {"1": "Notes", "2": "Other"},
    )
    assert "[citation:" not in stripped
    assert citations == [{"title": "Notes"}, {"title": "Other"}]


def test_unresolved_citation_is_stripped_without_a_title():
    stripped, citations = flatten_message_text(
        "Unknown [citation:https://example.com] marker.",
        {},
    )
    assert "[citation:" not in stripped
    assert citations == []


def test_fullwidth_and_zero_width_citation_markers_are_stripped():
    stripped, citations = flatten_message_text(
        "Per \u3010citation:11\u3011 and [\u200bcitation:22\u200b] done.",
        {"11": "Alpha", "22": "Beta"},
    )
    assert "citation:" not in stripped
    assert citations == [{"title": "Alpha"}, {"title": "Beta"}]


def test_url_citation_with_commas_is_not_split_into_chunk_ids():
    stripped, citations = flatten_message_text(
        "See [citation:https://news.example/7,114883,story.html].",
        {"114883": "Wrong"},
    )
    assert stripped == "See ."
    assert citations == []


def test_url_citation_payload_is_kept_whole():
    url = "https://news.example/7,114883,30573452,story.html"
    assert _citation_payloads(f"Per [citation:{url}] done.") == [url]


def test_numeric_citation_lists_still_split():
    assert _citation_payloads("[citation:11, doc-22,-33] and [citation:44]") == [
        "11",
        "doc-22",
        "-33",
        "44",
    ]


async def test_out_of_range_chunk_ids_are_not_queried():
    session = _Session([(7, "Seven")])

    titles = await _citation_titles(
        session, workspace_id=12, payloads={"7", "30573452000", "doc-5"}
    )

    assert titles == {"7": "Seven"}


async def test_no_query_when_no_payload_is_a_chunk_id():
    session = _Session()

    titles = await _citation_titles(
        session, workspace_id=12, payloads={"https://news.example/7,114883"}
    )

    assert titles == {}


class _Rows:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, *responses: list):
        self._responses = list(responses)

    async def execute(self, _stmt):
        return _Rows(self._responses.pop(0))


async def test_comma_separated_citation_keeps_every_title():
    when = datetime(2026, 6, 2, 14, tzinfo=UTC)
    message = SimpleNamespace(
        id=1,
        role="assistant",
        content="Both papers agree [citation:11, 22].",
        created_at=when,
    )
    thread = SimpleNamespace(id=5, title="Papers", created_at=when, messages=[message])
    session = _Session([thread], [(11, "Alpha"), (22, "Beta")])

    [exported] = await flatten_workspace_chats(session, workspace_id=12)

    [flat] = exported["messages"]
    assert "citation:" not in flat["text"]
    assert flat["citations"] == [{"title": "Alpha"}, {"title": "Beta"}]


async def test_citation_past_the_int_digit_limit_does_not_abort_the_export():
    # Past CPython's default 4300-digit limit, int() raises ValueError.
    huge = "9" * 5000
    when = datetime(2026, 6, 2, 14, tzinfo=UTC)
    message = SimpleNamespace(
        id=1,
        role="user",
        content=f"See [citation:{huge}] and [citation:7].",
        created_at=when,
    )
    thread = SimpleNamespace(id=5, title="Notes", created_at=when, messages=[message])
    session = _Session([thread], [(7, "Seven")])

    [exported] = await flatten_workspace_chats(session, workspace_id=12)

    [flat] = exported["messages"]
    assert flat["text"] == "See  and ."
    assert flat["citations"] == [{"title": "Seven"}]
