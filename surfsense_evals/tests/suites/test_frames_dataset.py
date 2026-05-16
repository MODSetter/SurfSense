"""Tests for the FRAMES dataset parser.

Network-free: we round-trip a tiny fixture TSV through pandas and
``load_questions`` to confirm:

* row indices become zero-padded ``Q###`` ids,
* ``wiki_links`` (Python list literal) is materialised correctly,
* ``reasoning_types`` is split on the pipe separator,
* missing Prompt/Answer rows are dropped, and
* the legacy ``wikipedia_link_*`` per-cell fallback works when
  ``wiki_links`` is missing/empty.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from surfsense_evals.suites.research.frames.dataset import (
    FramesQuestion,
    _parse_reasoning_types,
    _parse_wiki_links,
    load_questions,
)


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------


class TestParseWikiLinks:
    def test_python_list_literal(self) -> None:
        s = "['https://en.wikipedia.org/wiki/A', 'https://en.wikipedia.org/wiki/B']"
        assert _parse_wiki_links(s) == [
            "https://en.wikipedia.org/wiki/A",
            "https://en.wikipedia.org/wiki/B",
        ]

    def test_none_or_empty(self) -> None:
        assert _parse_wiki_links(None) == []
        assert _parse_wiki_links("") == []
        assert _parse_wiki_links("[]") == []

    def test_unquoted_csv_fallback(self) -> None:
        # Defensive: non-Python-list strings still split on commas.
        s = "https://a, https://b"
        assert _parse_wiki_links(s) == ["https://a", "https://b"]

    def test_already_a_list(self) -> None:
        assert _parse_wiki_links(["x", "y"]) == ["x", "y"]


class TestParseReasoningTypes:
    def test_pipe_separated(self) -> None:
        assert _parse_reasoning_types("Numerical reasoning | Multiple constraints") == [
            "Numerical reasoning",
            "Multiple constraints",
        ]

    def test_single_tag(self) -> None:
        assert _parse_reasoning_types("Tabular reasoning") == ["Tabular reasoning"]

    def test_empty(self) -> None:
        assert _parse_reasoning_types(None) == []
        assert _parse_reasoning_types("") == []


# ---------------------------------------------------------------------------
# Round-trip via pandas
# ---------------------------------------------------------------------------


def _write_tsv(path: Path, body: str) -> None:
    """Helper that writes a tab-separated fixture exactly as the user typed it."""

    path.write_text(textwrap.dedent(body), encoding="utf-8")


def test_load_questions_basic(tmp_path: Path) -> None:
    tsv = tmp_path / "test.tsv"
    rows = [
        # Header (first column is unnamed → pandas treats as index)
        "\tPrompt\tAnswer\twikipedia_link_1\twikipedia_link_2\treasoning_types\twiki_links",
        # Row 0
        "0\tWho was the 15th president?\tJames Buchanan\t"
        "https://en.wikipedia.org/wiki/James_Buchanan\t\t"
        "Multiple constraints\t"
        "['https://en.wikipedia.org/wiki/James_Buchanan']",
        # Row 1
        "1\tHow many years between A and B?\t87\t"
        "https://en.wikipedia.org/wiki/A\thttps://en.wikipedia.org/wiki/B\t"
        "Numerical reasoning | Temporal reasoning\t"
        "['https://en.wikipedia.org/wiki/A', 'https://en.wikipedia.org/wiki/B']",
        # Row 2 (intentionally missing Prompt — should be dropped)
        "2\t\tunused\t\t\t\t",
    ]
    tsv.write_text("\n".join(rows) + "\n", encoding="utf-8")

    questions = load_questions(tsv)
    assert len(questions) == 2

    q0, q1 = questions
    assert isinstance(q0, FramesQuestion)
    assert q0.qid == "Q000"
    assert q0.raw_index == 0
    assert q0.gold_answer == "James Buchanan"
    assert q0.wiki_urls == ["https://en.wikipedia.org/wiki/James_Buchanan"]
    assert q0.reasoning_types == ["Multiple constraints"]

    assert q1.qid == "Q001"
    assert q1.gold_answer == "87"
    assert q1.wiki_urls == [
        "https://en.wikipedia.org/wiki/A",
        "https://en.wikipedia.org/wiki/B",
    ]
    assert q1.reasoning_types == ["Numerical reasoning", "Temporal reasoning"]


def test_load_questions_falls_back_to_per_cell_links(tmp_path: Path) -> None:
    """When ``wiki_links`` is empty, the loader should glue the
    ``wikipedia_link_*`` cells back together."""

    tsv = tmp_path / "test.tsv"
    rows = [
        "\tPrompt\tAnswer\twikipedia_link_1\twikipedia_link_2\treasoning_types\twiki_links",
        "0\tQ?\tA\t"
        "https://en.wikipedia.org/wiki/Cell1\thttps://en.wikipedia.org/wiki/Cell2\t"
        "Numerical reasoning\t",
    ]
    tsv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    questions = load_questions(tsv)
    assert len(questions) == 1
    assert questions[0].wiki_urls == [
        "https://en.wikipedia.org/wiki/Cell1",
        "https://en.wikipedia.org/wiki/Cell2",
    ]


def test_load_questions_to_dict_round_trip(tmp_path: Path) -> None:
    tsv = tmp_path / "test.tsv"
    rows = [
        "\tPrompt\tAnswer\treasoning_types\twiki_links",
        "0\tQ?\tParis\tTemporal reasoning\t['https://en.wikipedia.org/wiki/Paris']",
    ]
    tsv.write_text("\n".join(rows) + "\n", encoding="utf-8")

    [q] = load_questions(tsv)
    d = q.to_dict()
    assert d["qid"] == "Q000"
    assert d["wiki_urls"] == ["https://en.wikipedia.org/wiki/Paris"]
    assert d["reasoning_types"] == ["Temporal reasoning"]
