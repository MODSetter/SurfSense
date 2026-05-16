"""Tests for the CRAG dataset loader (parser + sampling).

The full bz2 download is excluded — these tests synthesise a tiny
JSONL-bz2 in a tmp dir and verify the parser / stratified-sampler
produce well-shaped objects.
"""

from __future__ import annotations

import bz2
import json
from pathlib import Path

import pytest

from surfsense_evals.suites.research.crag.dataset import (
    CragPage,
    CragQuestion,
    iter_questions,
    stratified_sample,
)


def _make_jsonl_bz2(rows: list[dict], tmp_path: Path) -> Path:
    """Write ``rows`` as one JSON object per line, bz2-compressed."""

    dest = tmp_path / "fake.jsonl.bz2"
    payload = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    with bz2.open(dest, "wb") as fh:
        fh.write(payload)
    return dest


def _row(
    *,
    interaction_id: str,
    query: str,
    answer: str,
    domain: str = "movie",
    question_type: str = "simple",
    pages: list[dict] | None = None,
    alt_ans: list[str] | None = None,
    popularity: str = "head",
    static_or_dynamic: str = "static",
    split: int = 0,
    query_time: str = "2024-04-01",
) -> dict:
    return {
        "interaction_id": interaction_id,
        "query_time": query_time,
        "domain": domain,
        "question_type": question_type,
        "static_or_dynamic": static_or_dynamic,
        "query": query,
        "answer": answer,
        "alt_ans": alt_ans or [],
        "split": split,
        "popularity": popularity,
        "search_results": pages or [],
    }


class TestParser:
    def test_basic_parse(self, tmp_path: Path) -> None:
        rows = [
            _row(
                interaction_id="abc",
                query="Who directed Inception?",
                answer="Christopher Nolan",
                pages=[{
                    "page_name": "Inception (film)",
                    "page_url": "https://en.wikipedia.org/wiki/Inception",
                    "page_snippet": "snippet",
                    "page_result": "<html>full html</html>",
                    "page_last_modified": "2024-01-01",
                }],
            ),
        ]
        path = _make_jsonl_bz2(rows, tmp_path)
        parsed = iter_questions(path)
        assert len(parsed) == 1
        q = parsed[0]
        assert q.query == "Who directed Inception?"
        assert q.gold_answer == "Christopher Nolan"
        assert q.qid == "C00000"
        assert q.domain == "movie"
        assert q.question_type == "simple"
        assert len(q.pages) == 1
        page = q.pages[0]
        assert page.page_name == "Inception (film)"
        assert page.page_url == "https://en.wikipedia.org/wiki/Inception"

    def test_skips_missing_query_or_answer(self, tmp_path: Path) -> None:
        rows = [
            _row(interaction_id="1", query="", answer="x"),
            _row(interaction_id="2", query="ok?", answer=""),
            _row(interaction_id="3", query="ok?", answer="x"),
        ]
        path = _make_jsonl_bz2(rows, tmp_path)
        parsed = iter_questions(path)
        assert len(parsed) == 1
        assert parsed[0].interaction_id == "3"

    def test_skips_empty_pages(self, tmp_path: Path) -> None:
        rows = [
            _row(
                interaction_id="x",
                query="q?",
                answer="a",
                pages=[
                    {"page_url": "", "page_result": "<html/>"},  # no URL
                    {"page_url": "https://x.test/", "page_result": ""},  # empty html
                    {"page_url": "https://y.test/", "page_result": "<html>good</html>"},
                ],
            ),
        ]
        path = _make_jsonl_bz2(rows, tmp_path)
        parsed = iter_questions(path)
        assert len(parsed) == 1
        assert len(parsed[0].pages) == 1
        assert parsed[0].pages[0].page_url == "https://y.test/"

    def test_alt_answers_parsed(self, tmp_path: Path) -> None:
        rows = [
            _row(interaction_id="z", query="q?", answer="42",
                 alt_ans=["forty-two", "42.0"]),
        ]
        path = _make_jsonl_bz2(rows, tmp_path)
        parsed = iter_questions(path)
        assert parsed[0].alt_answers == ["forty-two", "42.0"]

    def test_handles_malformed_line(self, tmp_path: Path) -> None:
        # Manually construct a bz2 with one valid line and one garbage line.
        good = json.dumps(_row(interaction_id="ok", query="q?", answer="a"))
        path = tmp_path / "mixed.jsonl.bz2"
        with bz2.open(path, "wb") as fh:
            fh.write(b"not-json{\n")
            fh.write((good + "\n").encode("utf-8"))
        parsed = iter_questions(path)
        # Malformed line is skipped; one good row survives at index 1.
        assert len(parsed) == 1
        assert parsed[0].interaction_id == "ok"


class TestPageHash:
    def test_url_hash_stable(self) -> None:
        a = CragPage(
            page_name="A", page_url="https://x.test/p?q=1",
            page_snippet="", page_html="<html/>",
        )
        b = CragPage(
            page_name="B", page_url="https://x.test/p?q=1",
            page_snippet="", page_html="<html/>",
        )
        assert a.url_hash == b.url_hash
        assert len(a.url_hash) == 12

    def test_url_hash_unique(self) -> None:
        a = CragPage(
            page_name="A", page_url="https://x.test/a", page_snippet="", page_html="<html/>",
        )
        b = CragPage(
            page_name="B", page_url="https://x.test/b", page_snippet="", page_html="<html/>",
        )
        assert a.url_hash != b.url_hash


class TestStratifiedSample:
    def _make_pool(self) -> list[CragQuestion]:
        out: list[CragQuestion] = []
        idx = 0
        # 30 finance/simple, 20 movie/comparison, 5 sports/multi-hop.
        for n, domain, qtype in (
            (30, "finance", "simple"),
            (20, "movie", "comparison"),
            (5, "sports", "multi-hop"),
        ):
            for _ in range(n):
                out.append(CragQuestion(
                    qid=f"C{idx:05d}",
                    interaction_id=f"i{idx}",
                    query_time="2024-01-01",
                    query=f"q{idx}?",
                    gold_answer="a",
                    alt_answers=[],
                    domain=domain,
                    question_type=qtype,
                    static_or_dynamic="static",
                    popularity="head",
                    split=0,
                    raw_index=idx,
                    pages=[],
                ))
                idx += 1
        return out

    def test_sample_smaller_than_pool(self) -> None:
        pool = self._make_pool()
        sample = stratified_sample(pool, n=15, seed=7)
        assert len(sample) == 15
        # Should pull from all three buckets at least once.
        domains = {q.domain for q in sample}
        assert domains == {"finance", "movie", "sports"}

    def test_sample_returns_pool_when_n_geq(self) -> None:
        pool = self._make_pool()
        sample = stratified_sample(pool, n=999, seed=1)
        assert len(sample) == len(pool)

    def test_sample_sorted_by_raw_index(self) -> None:
        pool = self._make_pool()
        sample = stratified_sample(pool, n=10, seed=42)
        assert [q.raw_index for q in sample] == sorted(q.raw_index for q in sample)

    def test_sample_deterministic(self) -> None:
        pool = self._make_pool()
        s1 = stratified_sample(pool, n=20, seed=11)
        s2 = stratified_sample(pool, n=20, seed=11)
        assert [q.qid for q in s1] == [q.qid for q in s2]

    def test_n_zero_or_negative_returns_pool(self) -> None:
        pool = self._make_pool()
        assert len(stratified_sample(pool, n=0)) == len(pool)
        assert len(stratified_sample(pool, n=-1)) == len(pool)
