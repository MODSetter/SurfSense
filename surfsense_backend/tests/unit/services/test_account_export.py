"""Contract-3 producer: citation flattening and the committed fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services.export_service import flatten_message_text

pytestmark = pytest.mark.unit

def _contracts_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "plans" / "community-local" / "contracts"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("plans/community-local/contracts not found")


def test_committed_export_sample_matches_the_contract():
    spec = importlib.util.spec_from_file_location(
        "check_export_sample", _contracts_dir() / "check-export-sample.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(_contracts_dir() / "export-sample") == 0


def test_three_citation_markers_export_with_none_and_three_titles():
    text = (
        "A [citation:11] then [citation:22] and [citation:33] done."
    )
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
